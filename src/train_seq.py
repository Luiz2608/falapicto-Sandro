"""Compara N-gram, MLP, RNN e LSTM na tarefa 'prever o próximo card' (dados sintéticos).
Uso: python train_seq.py [--epochs 8] [--seeds 3]
Saídas: models/lstm.pt, docs/resultados_seq.json, docs/resultados_seq.md
"""
import json, time, argparse, collections, random
import numpy as np
import torch, torch.nn as nn
from core import ROOT, CARDS, ROTINAS

p = argparse.ArgumentParser()
p.add_argument("--epochs", type=int, default=8)
p.add_argument("--seeds", type=int, default=3)
p.add_argument("--data", default="seqs.jsonl")
p.add_argument("--tag", default="")
p.add_argument("--save", action="store_true", help="salva models/lstm.pt (usar só na v1, a que a API consome)")
args = p.parse_args()

CARD_IDS = list(CARDS)
PAD, EOS = 0, 1
CARD_OFF = 2
VOCAB = {c: i + CARD_OFF for i, c in enumerate(CARD_IDS)}
ROT_IDS = list(ROTINAS)
ROT_OFF = CARD_OFF + len(CARD_IDS)          # tokens de rotina vêm depois dos cards
V_IN = ROT_OFF + len(ROT_IDS)
N_OUT = CARD_OFF + len(CARD_IDS)            # saída: pad, eos, cards

rows = [json.loads(l) for l in open(ROOT / "data" / args.data, encoding="utf-8")]
random.Random(0).shuffle(rows)
cut = int(len(rows) * 0.85)
train_rows, test_rows = rows[:cut], rows[cut:]


def encode(r):
    rot = ROT_OFF + ROT_IDS.index(r["rotina"])
    toks = [VOCAB[t] for t in r["seq"]]
    return rot, toks


def make_seq_batch(rs):
    enc = [encode(r) for r in rs]
    L = max(len(t) for _, t in enc) + 1
    x = torch.zeros(len(rs), L, dtype=torch.long)
    y = torch.zeros(len(rs), L, dtype=torch.long)
    for i, (rot, toks) in enumerate(enc):
        inp = [rot] + toks
        tgt = toks + [EOS]
        x[i, :len(inp)] = torch.tensor(inp)
        y[i, :len(tgt)] = torch.tensor(tgt)
    return x, y


def make_mlp_data(rs):
    X, Y = [], []
    for r in rs:
        rot, toks = encode(r)
        full = toks + [EOS]
        for i, t in enumerate(full):
            p1 = toks[i - 1] if i >= 1 else PAD
            p2 = toks[i - 2] if i >= 2 else PAD
            X.append([rot, p2, p1]); Y.append(t)
    return torch.tensor(X), torch.tensor(Y)


class MLP(nn.Module):
    def __init__(s, emb=32, hid=128):
        super().__init__()
        s.e = nn.Embedding(V_IN, emb)
        s.f = nn.Sequential(nn.Linear(3 * emb, hid), nn.ReLU(), nn.Linear(hid, N_OUT))
    def forward(s, x):
        return s.f(s.e(x).flatten(1))


class Rec(nn.Module):
    def __init__(s, kind, emb=32, hid=64):
        super().__init__()
        s.e = nn.Embedding(V_IN, emb)
        s.r = (nn.LSTM if kind == "lstm" else nn.RNN)(emb, hid, batch_first=True)
        s.o = nn.Linear(hid, N_OUT)
    def forward(s, x):
        h, _ = s.r(s.e(x))
        return s.o(h)


def probe_rows():
    """frases onde o card final repete o objeto pedido antes ('eu quero X ... mais X')"""
    return [r for r in test_rows if len(r["seq"]) >= 4 and r["seq"][0] == "eu_quero" and r["seq"][-2] == "mais" and r["seq"][1] == r["seq"][-1]]


def probe_mlp(model):
    ok = 0; P = probe_rows()
    for r in P:
        rot, toks = encode(r)
        x = torch.tensor([[rot, toks[-3] if len(toks) >= 3 else PAD, toks[-2]]])
        with torch.no_grad(): lg = model(x)[0]
        lg[:CARD_OFF] = -1e9; ok += int(lg.argmax().item() == toks[-1])
    return ok / max(len(P), 1)


def probe_rec(model):
    ok = 0; P = probe_rows()
    for r in P:
        rot, toks = encode(r)
        x = torch.tensor([[rot] + toks[:-1]])
        with torch.no_grad(): lg = model(x)[0, -1]
        lg[:CARD_OFF] = -1e9; ok += int(lg.argmax().item() == toks[-1])
    return ok / max(len(P), 1)


def npar(m):
    return sum(p.numel() for p in m.parameters())


def topk_card_acc(logits, y, mask):
    """top1/top3 só sobre posições com alvo = card (ignora <eos> e pad)."""
    lg = logits.clone()
    lg[..., :CARD_OFF] = -1e9                # só cards como candidatos
    t3 = lg.topk(3, dim=-1).indices
    sel = mask
    t1 = (t3[..., 0] == y)[sel].float().mean().item()
    t3a = (t3 == y.unsqueeze(-1)).any(-1)[sel].float().mean().item()
    return t1, t3a


def train_eval(kind, seed):
    torch.manual_seed(seed); np.random.seed(seed)
    if kind == "mlp":
        model = MLP()
        Xtr, Ytr = make_mlp_data(train_rows); Xte, Yte = make_mlp_data(test_rows)
        opt = torch.optim.Adam(model.parameters(), 3e-3)
        for ep in range(args.epochs):
            perm = torch.randperm(len(Xtr))
            for i in range(0, len(perm), 256):
                b = perm[i:i + 256]
                loss = nn.functional.cross_entropy(model(Xtr[b]), Ytr[b])
                opt.zero_grad(); loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            lg = model(Xte)
        mask = Yte >= CARD_OFF
        t1, t3 = topk_card_acc(lg, Yte, mask)
        t0 = time.perf_counter()
        with torch.no_grad():
            for _ in range(200): model(Xte[:1])
        ms = (time.perf_counter() - t0) / 200 * 1000
    else:
        model = Rec(kind)
        opt = torch.optim.Adam(model.parameters(), 3e-3)
        for ep in range(args.epochs):
            order = list(range(len(train_rows))); random.Random(seed + ep).shuffle(order)
            for i in range(0, len(order), 256):
                x, y = make_seq_batch([train_rows[j] for j in order[i:i + 256]])
                lg = model(x)
                loss = nn.functional.cross_entropy(lg.reshape(-1, N_OUT), y.reshape(-1), ignore_index=PAD)
                opt.zero_grad(); loss.backward(); opt.step()
        model.eval()
        x, y = make_seq_batch(test_rows)
        with torch.no_grad():
            lg = model(x)
        mask = y >= CARD_OFF
        t1, t3 = topk_card_acc(lg, y, mask)
        x1 = x[:1, :3]
        t0 = time.perf_counter()
        with torch.no_grad():
            for _ in range(200): model(x1)
        ms = (time.perf_counter() - t0) / 200 * 1000
    return model, t1, t3, ms, (probe_mlp(model) if kind == 'mlp' else probe_rec(model))


def ngram_eval():
    cnt = collections.defaultdict(collections.Counter)
    for r in train_rows:
        prev = "<s>"
        for t in r["seq"]:
            cnt[(r["rotina"], prev)][t] += 1; prev = t
    h1 = h3 = n = 0
    for r in test_rows:
        prev = "<s>"
        for t in r["seq"]:
            top = [a for a, _ in cnt[(r["rotina"], prev)].most_common(3)]
            h1 += bool(top and top[0] == t); h3 += t in top; n += 1; prev = t
    P = probe_rows(); pk = 0
    for r in P:
        top = cnt[(r["rotina"], r["seq"][-2])].most_common(1)
        pk += bool(top and top[0][0] == r["seq"][-1])
    return h1 / n, h3 / n, pk / max(len(P), 1)


res = {}
t1, t3, pr = ngram_eval()
res["N-gram (bigrama)"] = {"params": 0, "top1": [t1], "top3": [t3], "ms": [0.0], "probe": [pr]}
best_lstm = None
for kind in ["mlp", "rnn", "lstm"]:
    name = {"mlp": "MLP (2 cards anteriores)", "rnn": "RNN", "lstm": "LSTM"}[kind]
    res[name] = {"params": 0, "top1": [], "top3": [], "ms": [], "probe": []}
    for s in range(args.seeds):
        m, a1, a3, ms, pr = train_eval(kind, s)
        res[name]["params"] = npar(m)
        res[name]["top1"].append(a1); res[name]["top3"].append(a3); res[name]["ms"].append(ms); res[name]["probe"].append(pr)
        if kind == "lstm" and s == 0:
            best_lstm = m
        print(f"{name} seed={s} top1={a1:.3f} top3={a3:.3f} retorno={pr:.3f} {ms:.2f}ms", flush=True)

(ROOT / "models").mkdir(exist_ok=True)
if args.save:
    torch.save({"state": best_lstm.state_dict(), "card_ids": CARD_IDS, "rot_ids": ROT_IDS}, ROOT / "models" / "lstm.pt")

(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / f"resultados_seq{args.tag}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
lines = ["| Modelo | Parâmetros | Top-1 | Top-3 | Acerto no card de retorno* | Latência/passo (ms) |", "|---|---|---|---|---|---|"]
for k, v in res.items():
    ms = lambda a: f"{np.mean(a):.2f}"
    f = lambda a: f"{np.mean(a)*100:.1f}% ± {np.std(a)*100:.1f}" if len(a) > 1 else f"{a[0]*100:.1f}%"
    lines.append(f"| {k} | {v['params']:,} | {f(v['top1'])} | {f(v['top3'])} | {(f(v['probe']) if probe_rows() else '—')} | {ms(v['ms'])} |")
(ROOT / "docs" / f"resultados_seq{args.tag}.md").write_text("\n".join(lines) + "\n\n*card final de \"eu quero X … mais X\" (n=%d no teste). Só há retorno nos dados v2.\n" % len(probe_rows()), encoding="utf-8")
print("\n".join(lines))
