"""
Tests for the two-stage indicator detector (docs/TASK_08_twostage.md; scripts/twostage/, scripts/06_run_twostage.py;
QUESTIONS.md item 18 decisions): the indicator schema matches the amended spec, the extraction prompt carries no
verdict word, parsing follows the frozen rules (first balanced object, normalisation before the vocabulary check,
missing key invalid, extra key ignored and counted, booleans with the synonym table), the volunteered-verdict
counter, the one-hot design without a failure level, a deterministic grouped-cv stage-2 fit on toy rows that
excludes parse failures, the config hash, and the runner's guards (model not in the three, eval with --limit,
eval off its tier, missing partition), which fire before any data or model is loaded. No model, no data needed.
Run from the repo root with `python -m unittest discover tests`.
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import load_config  # noqa: E402
from twostage.parse import (feature_names, featurize, first_balanced_object, parse_indicators,  # noqa: E402
                            schema_of, volunteered_verdict)
from twostage.stage2 import cluster_of, config_hash, fit_stage2, predict_row  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TCFG = load_config("twostage.yaml")
SCHEMA, NCFG = schema_of(TCFG), TCFG["parse"]["normalise"]
THREAT = ["urgency", "link_or_url", "sender_claim_inconsistency", "credential_or_payment_request", "grammar_anomaly",
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


def P(text):
    return parse_indicators(text, SCHEMA, NCFG)


class TestSchemaAndPrompt(unittest.TestCase):
    def test_schema_is_the_thirteen_keys_of_task_08_as_amended(self):
        self.assertEqual(list(SCHEMA), THREAT + ATTRS)
        for k in THREAT:
            self.assertEqual(SCHEMA[k], ["yes", "no", "unclear"])
        self.assertEqual(SCHEMA["is_question"], "bool")
        self.assertEqual(TCFG["models"], ["qwen25-7b", "gemma2-9b", "gemma2-27b"])
        self.assertIn("sender_claim_inconsistency", TCFG["definitions"])
        self.assertFalse(TCFG["parse"]["parse_failure_is_feature"])
        self.assertEqual(TCFG["stage2"]["cv"]["scheme"], "StratifiedGroupKFold")

    def test_prompt_has_sections_placeholders_and_no_verdict_words(self):
        text = (ROOT / TCFG["prompt"]).read_text(encoding="utf-8")
        for s in ("### system", "### user", "{subject}", "{body}"):
            self.assertIn(s, text)
        for w in TCFG["parse"]["verdict_words"] + ["suspicious", "verdict", "classify", "sender_domain_mismatch"]:
            self.assertIsNone(re.search(r"\b" + w + r"\b", text, flags=re.I), w)
        for k in SCHEMA:
            self.assertIn(f'"{k}"', text)

    def test_decoding_is_greedy_with_256_tokens(self):
        d = TCFG["decoding"]
        self.assertEqual((d["temperature"], d["top_p"], d["repeat_penalty"], d["max_tokens"]), (0.0, 1.0, 1.0, 256))


class TestParse(unittest.TestCase):
    def test_clean_object(self):
        ind, err, extra = P(json.dumps(good(urgency="yes", is_question=True)))
        self.assertIsNone(err); self.assertEqual(extra, [])
        self.assertEqual(ind["urgency"], "yes"); self.assertEqual(ind["is_question"], "true")

    def test_first_balanced_object(self):
        text = 'Here is the result:\n```json\n' + json.dumps(good()) + '\n```\n{"second": 1}'
        self.assertEqual(first_balanced_object(text), json.dumps(good()))
        self.assertEqual(first_balanced_object('{"a": "x } y", "b": {"c": 1}}'), '{"a": "x } y", "b": {"c": 1}}')
        self.assertIsNone(first_balanced_object("no braces here"))
        self.assertIsNone(first_balanced_object('{"unterminated": 1'))

    def test_normalisation_before_the_vocabulary_check(self):
        ind, err, _ = P(json.dumps(good(urgency="Yes", attachment=" NO ", sentiment="Positive", register="FORMAL")))
        self.assertIsNone(err)
        self.assertEqual((ind["urgency"], ind["attachment"], ind["sentiment"], ind["register"]), ("yes", "no", "positive", "formal"))
        for raw, want in (("yes", "true"), ("No", "false"), ("1", "true"), (0, "false"), (True, "true"), ("TRUE", "true")):
            ind, err, _ = P(json.dumps(good(is_question=raw)))
            self.assertIsNone(err, raw); self.assertEqual(ind["is_question"], want, raw)

    def test_failures_and_extra_keys(self):
        self.assertEqual(P("PHISHING")[:2], (None, "no_object"))
        self.assertEqual(P("[1, 2]")[1], "no_object")
        d = good(); del d["register"]
        self.assertEqual(P(json.dumps(d))[:2], (None, "missing_key"))
        self.assertEqual(P(json.dumps(good(urgency="maybe")))[:2], (None, "value_out_of_vocabulary"))
        self.assertEqual(P(json.dumps(good(urgency=True)))[:2], (None, "value_out_of_vocabulary"))   # true is not a ternary value
        self.assertEqual(P(json.dumps(good(is_question="maybe")))[:2], (None, "value_out_of_vocabulary"))
        ind, err, extra = P(json.dumps(good(verdict="x", confidence=0.9)))
        self.assertIsNone(err); self.assertEqual(extra, ["confidence", "verdict"]); self.assertNotIn("verdict", ind)

    def test_volunteered_verdict(self):
        words = TCFG["parse"]["verdict_words"]
        self.assertTrue(volunteered_verdict(json.dumps(good()) + "\nThis is phishing.", words))
        self.assertTrue(volunteered_verdict('{"verdict": "LEGITIMATE"}', words))
        self.assertFalse(volunteered_verdict(json.dumps(good()), words))
        self.assertFalse(volunteered_verdict("the phishingness", words))


class TestFeatures(unittest.TestCase):
    def test_one_hot_without_a_failure_level(self):
        names = feature_names(SCHEMA)
        self.assertEqual(len(names), 8 * 3 + 3 + 2 + 2 + 3 + 3)
        self.assertFalse(any(n.endswith("=invalid") for n in names))
        self.assertIn("urgency=unclear", names)
        v = featurize(parsed(urgency="yes"), SCHEMA)
        self.assertEqual(sum(v), 13); self.assertEqual(v[names.index("urgency=yes")], 1)
        with self.assertRaises(ValueError):
            featurize(None, SCHEMA)


class TestStage2(unittest.TestCase):
    def rows(self):
        rows = []
        for i in range(40):
            phish = i % 2 == 0
            ind = parsed(urgency="yes" if phish else "no", credential_or_payment_request="yes" if phish and i % 4 == 0 else "no")
            src = f"src{i // 2}"
            rows.append({"item_id": src if i % 4 < 2 else f"{src}#para_low", "label_true": "phish" if phish else "legit", "indicators": ind})
        rows.append({"item_id": "bad", "label_true": "phish", "indicators": None})
        return rows

    def test_fit_excludes_parse_failures_groups_by_source_and_is_deterministic(self):
        r1, r2 = fit_stage2(self.rows(), TCFG, 2026), fit_stage2(self.rows(), TCFG, 2026)
        self.assertEqual(r1["C"], r2["C"]); self.assertIn(r1["C"], TCFG["stage2"]["C_grid"])
        self.assertEqual(r1["coefficients"], r2["coefficients"])
        self.assertEqual((r1["n_rows"], r1["n_fitted"], r1["n_excluded_parse_failures"]), (41, 40, 1))
        self.assertEqual(r1["n_groups"], 20)
        self.assertEqual(r1["coefficients"][0]["feature"].split("=")[0], "urgency")
        label, p = predict_row(r1["model"], {"indicators": parsed(urgency="yes")}, TCFG)
        self.assertEqual(label, "phish"); self.assertGreaterEqual(p, 0.5)
        self.assertEqual(predict_row(r1["model"], {"indicators": parsed(urgency="no")}, TCFG)[0], "legit")
        self.assertEqual(predict_row(r1["model"], {"indicators": None}, TCFG), ("invalid", None))

    def test_cluster_of(self):
        self.assertEqual(cluster_of("nah:x:abc#para_high"), "nah:x:abc")
        self.assertEqual(cluster_of("eph:12"), "eph:12")

    def test_config_hash_covers_the_frozen_parts_only(self):
        h = config_hash(TCFG, 2026)
        self.assertEqual(len(h), 64)
        self.assertNotEqual(h, config_hash(TCFG, 2027))
        self.assertNotEqual(h, config_hash({**TCFG, "parse": {**TCFG["parse"], "verdict_words": []}}, 2026))
        self.assertNotEqual(h, config_hash({**TCFG, "definitions": {}}, 2026))
        self.assertEqual(h, config_hash({**TCFG, "budget": {}}, 2026))


class TestExtractStats(unittest.TestCase):
    def test_stats_from_extraction_rows_without_label_pred(self):
        runner = __import__("importlib").import_module("06_run_twostage")
        rows = [{"parse_ok": True, "parse_error": None, "extra_keys": [], "volunteered_verdict": False, "latency_s": 1.0,
                 "n_prompt_tokens": 300, "n_output_tokens": 100, "finish_reason": "stop", "truncated_input": False, "backend": "cpu"},
                {"parse_ok": False, "parse_error": "missing_key", "extra_keys": ["verdict"], "volunteered_verdict": True, "latency_s": 3.0,
                 "n_prompt_tokens": 320, "n_output_tokens": 256, "finish_reason": "length", "truncated_input": False, "backend": "cpu"}]
        st = runner.extract_stats(rows)
        self.assertEqual((st["n"], st["parse_failures"], st["parse_failure_rate"]), (2, 1, 0.5))
        self.assertEqual(st["parse_errors"], {"missing_key": 1}); self.assertEqual(st["extra_keys_seen"], {"verdict": 1})
        self.assertEqual((st["volunteered_verdicts"], st["latency_median_s"], st["output_tokens_mean"]), (1, 2.0, 178.0))
        self.assertEqual(st["finish_reasons"], {"stop": 1, "length": 1})
        self.assertEqual(runner.extract_stats([])["n"], 0)


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

    def test_smoke_on_eval_is_refused(self):
        code, out = self.run_cli("extract", "--model", "qwen25-7b", "--partition", "eval", "--tier", "colab_t4", "--smoke")
        self.assertNotEqual(code, 0); self.assertIn("dev smoke sample only", out)

    def test_partition_required(self):
        code, out = self.run_cli("predict", "--model", "qwen25-7b")
        self.assertNotEqual(code, 0); self.assertIn("--partition", out)


if __name__ == "__main__":
    unittest.main()
