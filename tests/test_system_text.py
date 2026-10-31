"""
System text delivery (QUESTIONS.md item 13): for every model in configs/models.yaml whose GGUF is present,
render the zero_shot and role prompts exactly as llama-cpp-python's create_chat_completion would (vocabulary
only, no weights) and check that (1) the system text appears in the rendered prompt, (2) the role prompt is
longer than the zero_shot prompt by the tokens of the extra system text (within 2 tokens for boundary
effects), and (3) the configuration is consistent with the guard in detect.backend: a model that llama-cpp-
python formats with a built-in formatter must have system_role false. Models whose GGUF is not on this
machine are skipped by name (the notebook runs this test on Colab after downloading its tier).
Run from the repo root with `python -m unittest tests.test_system_text`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from common import ROOT, load_config  # noqa: E402
from detect.prompts import load_prompt, render, messages  # noqa: E402

try:
    import llama_cpp  # noqa: E402
    from detect.backend import render_chat_prompt, uses_builtin_formatter  # noqa: E402
except ImportError:            # pragma: no cover
    llama_cpp = None

SUBJECT, BODY = "Quarterly report attached", "Hi team, please find the quarterly report attached. Regards, Dana"


def _vocab(path):
    return llama_cpp.Llama(model_path=str(path), vocab_only=True, verbose=False)


def _n_tokens(llm, text):
    return len(llm.tokenize(text.encode("utf-8"), add_bos=False, special=False))


class SystemTextDelivered(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if llama_cpp is None:
            raise unittest.SkipTest("llama_cpp not installed")
        cls.dcfg, cls.mcfg = load_config("detection.yaml"), load_config("models.yaml")
        cls.prompts = {s: load_prompt(cls.dcfg, s) for s in ("zero_shot", "role")}

    def _present(self):
        present, absent = {}, []
        for key, e in self.mcfg["models"].items():
            path = ROOT / self.mcfg["local_dir"] / e["gguf_file"]
            (present.__setitem__(key, path) if path.exists() else absent.append(key))
        if not present:
            self.skipTest("no GGUF present; run scripts/06_download_models.py")
        return present, absent

    def test_system_text_reaches_every_model(self):
        present, absent = self._present()
        for key, path in present.items():
            e = self.mcfg["models"][key]
            llm = _vocab(path)
            with self.subTest(model=key, chat_format=llm.chat_format):
                rendered, n = {}, {}
                for s, p in self.prompts.items():
                    system, user = render(p, SUBJECT, BODY)
                    rendered[s] = render_chat_prompt(llm, messages(system, user, e["system_role"]))
                    n[s] = _n_tokens(llm, rendered[s])
                    self.assertIn(system, rendered[s], f"{key}/{s}: system text missing from the rendered prompt")
                    self.assertIn(user, rendered[s], f"{key}/{s}: user text missing from the rendered prompt")
                extra = _n_tokens(llm, self.prompts["role"]["system"]) - _n_tokens(llm, self.prompts["zero_shot"]["system"])
                self.assertGreater(extra, 0, "the role system text must be longer than the zero_shot one")
                self.assertGreater(n["role"], n["zero_shot"], f"{key}: role prompt not longer than zero_shot")
                self.assertLessEqual(abs((n["role"] - n["zero_shot"]) - extra), 2,
                                     f"{key}: role minus zero_shot is {n['role'] - n['zero_shot']} tokens, "
                                     f"the system texts differ by {extra}")
        if absent:
            print(f"\n[test_system_text] GGUF not present, not checked here: {absent}", file=sys.stderr)

    def test_builtin_formatter_implies_system_role_false(self):
        present, _ = self._present()
        for key, path in present.items():
            llm = _vocab(path)
            with self.subTest(model=key, chat_format=llm.chat_format):
                if uses_builtin_formatter(llm):
                    self.assertFalse(self.mcfg["models"][key]["system_role"],
                                     f"{key}: built-in formatter {llm.chat_format!r} with system_role true "
                                     f"(the guard in detect.backend would refuse to run it)")


if __name__ == "__main__":
    unittest.main()
