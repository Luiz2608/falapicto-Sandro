"""Compara as versões quantizadas do SLM (f16, q8_0, q4_k_m...): tamanho, latência, acerto e formato.

1) Suba um llama-server POR modelo, em portas diferentes (um terminal para cada):
     llama-server -m gguf_f16/modelo.gguf    --port 8081
     llama-server -m gguf_q8_0/modelo.gguf   --port 8082
     llama-server -m gguf_q4_k_m/modelo.gguf --port 8083
2) Rode (NOME|URL|ARQUIVO.gguf — o arquivo só serve para medir o tamanho):
     python benchmark_slm.py \
       --modelo "f16|http://localhost:8081/v1/chat/completions|gguf_f16/modelo.gguf" \
       --modelo "q8_0|http://localhost:8082/v1/chat/completions|gguf_q8_0/modelo.gguf" \
       --modelo "q4_k_m|http://localhost:8083/v1/chat/completions|gguf_q4_k_m/modelo.gguf"
Usa o mesmo conjunto de TESTE do notebook (10% finais de data/slm_train.jsonl, embaralhado com seed 0).
Saída: docs/resultados_slm.md e .json
"""
import re, json, time, random, argparse, statistics
from pathlib import Path
import httpx
from core import ROOT, extrair_resposta, rule_sentence, ordenar
from slm_dataset import verificar, LABEL2ID

ap = argparse.ArgumentParser()
ap.add_argument("--modelo", action="append", required=True, help="NOME|URL|ARQUIVO.gguf")
ap.add_argument("--dados", default=str(ROOT / "data" / "slm_train.jsonl"))
ap.add_argument("--n", type=int, default=200, help="máximo de exemplos de teste")
ap.add_argument("--tag", default="")
a = ap.parse_args()

rows = [json.loads(l) for l in open(a.dados, encoding="utf-8") if l.strip()]
random.Random(0).shuffle(rows)                    # mesma divisão do notebook
teste = rows[int(len(rows) * 0.9):][: a.n]
if not teste:
    raise SystemExit("Sem exemplos de teste: gere mais dados (slm_train.jsonl).")


def norm(s):
    return re.sub(r"[^\wà-ú ]", "", s.lower()).strip()


def pedir(url, r):
    msgs = [{"role": {"system": "system", "human": "user"}[m["from"]], "content": m["value"]} for m in r["conversations"][:2]]
    t0 = time.perf_counter()
    j = httpx.post(url, json={"messages": msgs, "max_tokens": 128, "temperature": 0.0}, timeout=60).json()
    ms = (time.perf_counter() - t0) * 1000
    txt = j["choices"][0]["message"]["content"]
    ntok = (j.get("usage") or {}).get("completion_tokens")
    return txt, ms, ntok


res = []
for spec in a.modelo:
    nome, url, arq = (spec.split("|") + [""])[:3]
    for r in teste[:2]:
        pedir(url, r)                              # aquecimento (não conta)
    ok = fmt = fiel = ok_sr = n_sr = 0; lat = []; toks = []; erros = []
    for r in teste:
        gold = extrair_resposta(r["conversations"][2]["value"])
        txt, ms, ntok = pedir(url, r)
        pred = extrair_resposta(txt)
        ids = ordenar([LABEL2ID[x.strip().lower()] for x in r["conversations"][1]["value"].replace("Cards:", "").split(",")])
        lat.append(ms); fmt += "<resposta>" in txt
        igual = norm(pred) == norm(gold); ok += igual
        fiel += verificar(ids, pred) is None             # fiel: não omite nem inventa conteúdo dos cards
        if not rule_sentence(ids):                       # combinações que as regras NÃO cobrem = trabalho real do SLM
            n_sr += 1; ok_sr += igual
        if not igual: erros.append((r["conversations"][1]["value"], gold, pred))
        if ntok: toks.append(ntok / (ms / 1000))
    mb = Path(arq).stat().st_size / 1e6 if arq and Path(arq).exists() else None
    lat.sort()
    res.append({"modelo": nome, "mb": mb, "exato": ok / len(teste), "exato_sem_regra": (ok_sr / n_sr) if n_sr else None, "n_sem_regra": n_sr,
                "fiel": fiel / len(teste), "formato": fmt / len(teste), "erros": erros[:15],
                "lat_media": statistics.mean(lat), "lat_p95": lat[int(0.95 * (len(lat) - 1))],
                "tok_s": statistics.mean(toks) if toks else None, "n": len(teste)})
    print(f"{nome}: exato={res[-1]['exato']:.0%} lat={res[-1]['lat_media']:.0f} ms", flush=True)

md = ["| Modelo | Tamanho (MB) | Acerto exato | Exato (só combinações sem regra) | Fiel aos cards | Formato válido | Latência média (ms) | Latência p95 (ms) | Tokens/s |", "|---|---|---|---|---|---|---|---|---|"]
for r in res:
    sr = f"{r['exato_sem_regra']:.1%} (n={r['n_sem_regra']})" if r["exato_sem_regra"] is not None else "—"
    md.append(f"| {r['modelo']} | {'%.0f' % r['mb'] if r['mb'] else '—'} | {r['exato']:.1%} | {sr} | {r['fiel']:.1%} | {r['formato']:.1%} | {r['lat_media']:.0f} | {r['lat_p95']:.0f} | {'%.1f' % r['tok_s'] if r['tok_s'] else '—'} |")
md2 = []
for r in res:
    md2.append(f"\n**Erros de {r['modelo']}** (até 15):\n")
    md2 += [f"- `{e[0]}` → esperado: {e[1]} | modelo: {e[2]}" for e in r["erros"]]
rodape = f"\n{len(teste)} exemplos de teste · temperatura 0 · latência medida ponta a ponta na máquina atual."
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / f"resultados_slm{a.tag}.md").write_text("\n".join(md) + rodape + "\n" + "\n".join(md2) + "\n", encoding="utf-8")
(ROOT / "docs" / f"resultados_slm{a.tag}.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
print("\n".join(md) + rodape)
