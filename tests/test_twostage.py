"""
Tests for the two-stage indicator detector (docs/TASK_08_twostage.md; scripts/twostage/, scripts/06_run_twostage.py):
the indicator schema matches the spec, the extraction prompt carries no verdict word, parsing follows the frozen
rules (first balanced object, missing / unknown key, vocabulary, booleans), the volunteered-verdict check, the
one-hot design with the explicit invalid level, a deterministic stage-2 fit on toy rows, the config hash, and the
runner's guards (model not in the three, eval with --limit, missing partition), which fire before any data or
model is loaded. No model, no data needed. Run from the repo root with `python -m unittest discover tests`.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import load_config  # noqa: E402
from twostage.parse import (feature_names, featurize, first_balanced_object, parse_indicators,  # noqa: E402
                            schema_of, volunteered_verdict)
from twostage.stage2 import config_hash, fit_stage2, predict_row  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TCFG = load_config("twostage.yaml")
SCHEMA = schema_of(TCFG)
THREAT = ["urgency", "link_or_url", "sender_domain_mismatch", "credential_or_payment_request", "grammar_anomaly",
          "impersonation_authority", "attachment", "generic_greeting"]
ATTRS = ["sentiment", "is_question", "is_complaint", "language_pattern", "register"]


def good(**over):
    d = {k: "no" for k in THREAT}
    d.update({"sentiment": "neutral", "is_question": False, "is_complaint": False, "language_pattern": "human_like", "register": "formal"})
    d.update(over)
    return d


def parsed(**over):
    """good() as parse_indicators returns it: booleans as the strings "true" / "false"."""
    return {k: ("true" if v is True else "false" if v is False else v) for k, v in good(**over).items()}


def dumps(d):
    import json
    return json.dumps(d)


class TestSchemaAndPrompt(unittest.TestCase):
    def test_schema_is_the_thirteen_keys_of_task_08(self):
        self.assertEqual(list(SCHEMA), THREAT + ATTRS)
        for k in THREAT:
            self.assertEqual(SCHEMA[k], ["yes", "no", "unclear"])
        self.assertEqual(SCHEMA["is_question"], "bool")
        self.assertEqual(SCHEMA["sentiment"], ["negative", "neutral", "positive"])
        self.assertEqual(TCFG["models"], ["qwen25-7b", "gemma2-9b", "gemma2-27b"])

    def test_prompt_has_sections_placeholders_and_no_verdict_words(self):
        text = (ROOT / TCFG["prompt"]).read_text(encoding="utf-8")
        self.assertIn("### system", text)
        self.assertIn("### user", text)
        self.assertIn("{subject}", text)
        self.assertIn("{body}", text)
        for w in TCFG["parse"]["verdict_words"] + ["suspicious", "verdict", "classify"]:
            self.assertIsNone(re.search(r"\b" + w + r"\b", text, flags=re.I), w)
        for k in SCHEMA:
            self.assertIn(f'"{k}"', text)

    def test_decoding_is_greedy_with_256_tokens(self):
        d = TCFG["decoding"]
        self.assertEqual((d["temperature"], d["top_p"], d["repeat_penalty"], d["max_tokens"]), (0.0, 1.0, 1.0, 256))


class TestParse(unittest.TestCase):
    def test_clean_object(self):
        ind, err = parse_indicators(dumps(good(urgency="yes", is_question=True)), SCHEMA)
        self.assertIsNone(err)
        self.assertEqual(ind["urgency"], "yes")
        self.assertEqual(ind["is_question"], "true")

    def test_first_balanced_object_ignores_prose_fences_and_braces_in_strings(self):
        text = 'Here is the result:\n```json\n' + dumps(good()) + '\n```\n{"second": 1}'
        self.assertEqual(first_balanced_object(text), dumps(good()))
        self.assertEqual(first_balanced_object('{"a": "x } y", "b": {"c": 1}}'), '{"a": "x } y", "b": {"c": 1}}')
        self.assertIsNone(first_balanced_object("no braces here"))
        self.assertIsNone(first_balanced_object('{"unterminated": 1'))

    def test_failures(self):
        self.assertEqual(parse_indicators("PHISHING", SCHEMA), (None, "no_object"))
        self.assertEqual(parse_indicators("[1, 2]", SCHEMA)[1], "no_object")
        d = good(); del d["register"]
        self.assertEqual(parse_indicators(dumps(d), SCHEMA), (None, "missing_key"))
        self.assertEqual(parse_indicators(dumps(good(verdict="phishing")), SCHEMA), (None, "unknown_key"))
        self.assertEqual(parse_indicators(dumps(good(urgency="maybe")), SCHEMA), (None, "value_out_of_vocabulary"))
        self.assertEqual(parse_indicators(dumps(good(urgency=True)), SCHEMA), (None, "value_out_of_vocabulary"))
        self.assertEqual(parse_indicators(dumps(good(is_question="yes")), SCHEMA), (None, "non_boolean"))
        self.assertEqual(parse_indicators('{"urgency": "yes", }', SCHEMA), (None, "no_object"))

    def test_volunteered_verdict(self):
        words = TCFG["parse"]["verdict_words"]
        self.assertTrue(volunteered_verdict(dumps(good()) + "\nThis is phishing.", words))
        self.assertTrue(volunteered_verdict('{"verdict": "LEGITIMATE"}', words))
        self.assertFalse(volunteered_verdict(dumps(good()), words))
        self.assertFalse(volunteered_verdict("the phishingness", words))


class TestFeatures(unittest.TestCase):
    def test_one_hot_with_explicit_invalid_level(self):
        names = feature_names(SCHEMA)
        self.assertEqual(len(names), 8 * 4 + 4 + 3 + 3 + 4 + 4)
        self.assertIn("urgency=invalid", names)
        self.assertIn("is_question=true", names)
        v = featurize(parsed(urgency="yes"), SCHEMA)
        self.assertEqual(sum(v), 13)
        self.assertEqual(v[names.index("urgency=yes")], 1)
        self.assertEqual(v[names.index("urgency=invalid")], 0)
        vi = featurize(None, SCHEMA)
        self.assertEqual(sum(vi), 13)
        self.assertEqual([names[i] for i, x in enumerate(vi) if x], [n for n in names if n.endswith("=invalid")])


class TestStage2(unittest.TestCase):
    def rows(self):
        rows = []
        for i in range(40):
            phish = i % 2 == 0
            ind = parsed(urgency="yes" if phish else "no", credential_or_payment_request="yes" if phish and i % 4 == 0 else "no")
            rows.append({"item_id": f"i{i}", "label_true": "phish" if phish else "legit", "indicators": ind})
        rows.append({"item_id": "bad", "label_true": "phish", "indicators": None})
        return rows

    def test_fit_is_deterministic_and_predicts(self):
        r1, r2 = fit_stage2(self.rows(), TCFG, 2026), fit_stage2(self.rows(), TCFG, 2026)
        self.assertEqual(r1["C"], r2["C"])
        self.assertIn(r1["C"], TCFG["stage2"]["C_grid"])
        self.assertEqual(r1["coefficients"], r2["coefficients"])
        self.assertEqual(r1["n_parse_failures"], 1)
        self.assertEqual(r1["coefficients"][0]["feature"].split("=")[0], "urgency")
        label, p = predict_row(r1["model"], {"indicators": parsed(urgency="yes")}, TCFG)
        self.assertEqual(label, "phish"); self.assertGreaterEqual(p, 0.5)
        label, p = predict_row(r1["model"], {"indicators": parsed(urgency="no")}, TCFG)
        self.assertEqual(label, "legit")
        self.assertEqual(predict_row(r1["model"], {"indicators": None}, TCFG), ("invalid", None))

    def test_config_hash_covers_indicators_and_seed(self):
        h = config_hash(TCFG, 2026)
        self.assertEqual(len(h), 64)
        self.assertNotEqual(h, config_hash(TCFG, 2027))
        t2 = {**TCFG, "parse": {**TCFG["parse"], "verdict_words": []}}
        self.assertNotEqual(h, config_hash(t2, 2026))
        t3 = {**TCFG, "budget": {}}
        self.assertEqual(h, config_hash(t3, 2026))


class TestRunnerGuards(unittest.TestCase):
    def run_cli(self, *args):
        r = subprocess.run([sys.executable, "scripts/06_run_twostage.py", *args], cwd=ROOT, capture_output=True, text=True)
        return r.returncode, (r.stdout + r.stderr)

    def test_model_outside_the_three_is_refused(self):
        code, out = self.run_cli("extract", "--model", "llama31-8b", "--partition", "dev")
        self.assertNotEqual(code, 0); self.assertIn("three, no more", out)

    def test_eval_with_limit_is_refused(self):
        code, out = self.run_cli("extract", "--model", "qwen25-7b", "--partition", "eval", "--tier", "colab_t4", "--limit", "5")
        self.assertNotEqual(code, 0); self.assertIn("dev only", out)

    def test_eval_off_its_tier_is_refused(self):
        code, out = self.run_cli("extract", "--model", "gemma2-27b", "--partition", "eval", "--tier", "colab_t4")
        self.assertNotEqual(code, 0); self.assertIn("colab_l4", out)

    def test_partition_required(self):
        code, out = self.run_cli("predict", "--model", "qwen25-7b")
        self.assertNotEqual(code, 0); self.assertIn("--partition", out)


if __name__ == "__main__":
    unittest.main()
