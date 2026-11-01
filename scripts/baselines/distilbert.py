"""
distilbert.py — the fine-tuned transformer baseline of configs/baselines.yaml (TASK_06 section 3: DistilBERT
base uncased, 3 epochs, lr 2e-5, batch 16, max 512 tokens, fixed seed; Colab T4, notebooks/cloud_baselines.ipynb).
Plain PyTorch loop, no Trainer: every source of randomness is seeded, the data order is drawn from a seeded
generator, cuDNN runs deterministically and fp32 is used throughout. The checkpoint (state_dict) is written to
models/baselines/ (gitignored, copied to Drive) and its sha256 is the model_hash of every results row. torch
and transformers are imported lazily so that the TF-IDF baselines run without them.
"""
import os
import time

LABELS = ["legit", "phish"]           # class ids 0 and 1; p_phish = softmax[:, 1]


def set_determinism(seed: int, deterministic: bool) -> None:
    """Seeds and deterministic kernels. CUBLAS_WORKSPACE_CONFIG must be set before the first CUDA call."""
    import random
    import numpy as np
    import torch
    if deterministic:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    if deterministic:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        torch.use_deterministic_algorithms(True, warn_only=True)


def load(entry: dict, device: str) -> dict:
    """Tokeniser and classification head on the pretrained encoder; records the Hugging Face snapshot commit."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    name, rev = entry["pretrained"], entry["revision"]
    tok = AutoTokenizer.from_pretrained(name, revision=rev)
    model = AutoModelForSequenceClassification.from_pretrained(
        name, revision=rev, num_labels=len(LABELS), id2label=dict(enumerate(LABELS)),
        label2id={l: i for i, l in enumerate(LABELS)})
    model.to(device)
    sha = getattr(model.config, "_commit_hash", None)
    if sha is None:
        try:
            from huggingface_hub import model_info
            sha = model_info(name, revision=rev).sha
        except Exception:        # offline or API change: recorded as unknown, not fatal
            sha = "unknown"
    return {"tokenizer": tok, "model": model, "device": device, "pretrained": name, "snapshot_sha": sha,
            "torch": torch.__version__, "transformers": __import__("transformers").__version__}


def encode(tok, texts: list, max_length: int):
    return tok(texts, truncation=True, max_length=max_length, padding=True, return_tensors="pt")


def train(m: dict, entry: dict, texts: list, y: list, seed: int, log=print) -> dict:
    """Fixed schedule, no early stopping, no selection: the weights after the last epoch are the model."""
    import torch
    from transformers import get_linear_schedule_with_warmup
    model, tok, dev = m["model"], m["tokenizer"], m["device"]
    labels = torch.tensor([LABELS.index(v) for v in y])
    n, bs, epochs = len(texts), entry["batch_size"], entry["epochs"]
    steps_per_epoch = (n + bs - 1) // bs
    total = steps_per_epoch * epochs
    opt = torch.optim.AdamW(model.parameters(), lr=entry["learning_rate"], weight_decay=entry["weight_decay"])
    sched = get_linear_schedule_with_warmup(opt, int(entry["warmup_ratio"] * total), total)
    gen = torch.Generator().manual_seed(seed)
    t0, losses, step = time.perf_counter(), [], 0
    model.train()
    for ep in range(epochs):
        order = torch.randperm(n, generator=gen).tolist()
        ep_loss = 0.0
        for b in range(0, n, bs):
            idx = order[b:b + bs]
            enc = encode(tok, [texts[i] for i in idx], entry["max_length"]).to(dev)
            out = model(**enc, labels=labels[idx].to(dev))
            out.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad(set_to_none=True)
            ep_loss += out.loss.item() * len(idx)
            step += 1
            if step % 50 == 0 or step == total:
                log(f"[distilbert] epoch {ep + 1}/{epochs} step {step}/{total} loss {out.loss.item():.4f} "
                    f"elapsed {(time.perf_counter() - t0) / 60:.1f} min")
        losses.append(round(ep_loss / n, 5))
    model.eval()
    return {"epoch_mean_loss": losses, "steps": total, "steps_per_epoch": steps_per_epoch,
            "train_s": round(time.perf_counter() - t0, 1), "n_train": n,
            "n_train_truncated": sum(1 for t in texts if len(tok(t)["input_ids"]) > entry["max_length"])}


def save_checkpoint(m: dict, path) -> str:
    import torch
    from baselines.core import sha256_bytes
    torch.save({k: v.detach().cpu() for k, v in m["model"].state_dict().items()}, path)
    return sha256_bytes(path.read_bytes())


def load_checkpoint(m: dict, path) -> str:
    import torch
    from baselines.core import sha256_bytes
    m["model"].load_state_dict(torch.load(path, map_location=m["device"]))
    m["model"].eval()
    return sha256_bytes(path.read_bytes())


def score_one(m: dict, text: str, max_length: int) -> tuple:
    """(p_phish, tokens fed to the model, truncated?) for one item; timing is done by the caller."""
    import torch
    tok = m["tokenizer"]
    full = len(tok(text)["input_ids"])
    enc = encode(tok, [text], max_length).to(m["device"])
    with torch.no_grad():
        logits = m["model"](**enc).logits
    p = torch.softmax(logits.float(), dim=-1)[0, LABELS.index("phish")].item()
    return float(p), int(enc["input_ids"].shape[1]), full > max_length
