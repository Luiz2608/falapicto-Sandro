"""Mede o acerto do YOLO POR OBJETO, do jeito que o produto usa (mesmo mapeamento e limiar da API).

Organize suas fotos assim (nome da pasta = id do card, veja data/cards.json):
    fotos/copo/1.jpg  fotos/copo/2.jpg  fotos/bola/1.jpg  fotos/lapis/1.jpg ...
Rode:  python avaliar_yolo.py fotos                 # YOLO pré-treinado (COCO) com o mapeamento da API
       python avaliar_yolo.py fotos --pesos best.pt --classes-sao-cards   # modelo ajustado (classes = ids dos cards)
Saída: tabela no terminal + docs/resultados_yolo.md + docs/resultados_yolo.csv
"""
import sys, csv, argparse, time
from pathlib import Path
from core import ROOT, DATA, CARDS

ap = argparse.ArgumentParser()
ap.add_argument("pasta")
ap.add_argument("--pesos", default=None)
ap.add_argument("--conf", type=float, default=0.35, help="mesmo limiar da API (0.35)")
ap.add_argument("--classes-sao-cards", action="store_true", help="pesos ajustados: nomes das classes já são ids de cards")
ap.add_argument("--tag", default="")
a = ap.parse_args()

from ultralytics import YOLO
local = ROOT / "models" / "yolov8n.pt"
pesos = a.pesos or (str(local) if local.exists() else "yolov8n.pt")
model = YOLO(pesos)
mapa = {} if a.classes_sao_cards else DATA["objetos_coco"]
mapeados = set(CARDS) if a.classes_sao_cards else set(mapa.values())

IMG = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
linhas, por_classe, tempos = [], {}, []
for pasta in sorted(p for p in Path(a.pasta).iterdir() if p.is_dir()):
    cid = pasta.name
    if cid not in CARDS:
        print(f"[aviso] pasta '{cid}' não é um id de card (veja data/cards.json) — ignorada"); continue
    st = por_classe.setdefault(cid, {"n": 0, "acertou": 0, "errou": 0, "nada": 0, "mapeado": cid in mapeados})
    for f in sorted(x for x in pasta.iterdir() if x.suffix.lower() in IMG):
        t0 = time.perf_counter()
        r = model(str(f), verbose=False, conf=a.conf)[0]
        tempos.append((time.perf_counter() - t0) * 1000)
        previstos = {(n if a.classes_sao_cards else mapa.get(n)) for n in (r.names[int(b.cls)] for b in r.boxes)} - {None}
        res = "acertou" if cid in previstos else ("errou" if previstos else "nada")
        st["n"] += 1; st[res] += 1
        linhas.append([cid, f.name, res, ",".join(sorted(previstos))])

tot = {k: sum(v[k] for v in por_classe.values()) for k in ("n", "acertou", "errou", "nada")}
md = ["| Objeto (card) | Fotos | Acertou | Errou (outro objeto) | Não viu nada | Acerto |", "|---|---|---|---|---|---|"]
for cid, v in por_classe.items():
    if not v["mapeado"]:
        md.append(f"| {CARDS[cid]['label']} | {v['n']} | — | — | — | *sem classe no modelo (precisa de ajuste fino)* |")
    else:
        md.append(f"| {CARDS[cid]['label']} | {v['n']} | {v['acertou']} | {v['errou']} | {v['nada']} | {v['acertou']/max(v['n'],1)*100:.0f}% |")
av = [v for v in por_classe.values() if v["mapeado"]]
n_av = sum(v["n"] for v in av); ac_av = sum(v["acertou"] for v in av)
md.append(f"| **Total (classes que o modelo conhece)** | {n_av} | {ac_av} | | | **{ac_av/max(n_av,1)*100:.0f}%** |")
rodape = f"\nPesos: `{Path(pesos).name}` · limiar de confiança: {a.conf} · latência média por foto (CPU): {sum(tempos)/max(len(tempos),1):.0f} ms · {tot['n']} fotos."
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / f"resultados_yolo{a.tag}.md").write_text("\n".join(md) + rodape + "\n", encoding="utf-8")
with open(ROOT / "docs" / f"resultados_yolo{a.tag}.csv", "w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows([["card", "foto", "resultado", "previstos"]] + linhas)
print("\n".join(md) + rodape)
