"""Junta datasets YOLOv8 baixados do Roboflow Universe em UM dataset com as classes do FalaPicto.

Uso:
  1) Baixe 2-4 datasets (botão "Download Dataset" > formato YOLOv8) e extraia cada um numa pasta dentro de `baixados/`:
        baixados/ds1/{train,valid,test,data.yaml}   baixados/ds2/...
  2) python mesclar_datasets.py baixados saida
     (a pasta `saida` vira o dataset final, com data.yaml; suba o zip dela no notebook 04_yolo_ajuste.ipynb)
Os nomes de classe de cada dataset são convertidos pelo MAPA abaixo (minúsculas, sem espaços/hífens).
Classes que não estão no MAPA são descartadas. Imagens que ficam sem nenhuma caixa são ignoradas.
Classes que NÃO são cards (apontador, borracha...) ficam no modelo de propósito: servem para a API NÃO confundir
um apontador com 'copo' (a caixa delas suprime a detecção errada do YOLO pré-treinado).
"""
import sys, shutil, re, collections
from pathlib import Path
import yaml

MAPA = {  # nome no dataset de origem (normalizado) -> classe final
    "pencil": "lapis", "pensil": "lapis", "lead": "lapis", "pencils": "lapis",
    "pen": "caneta", "ballpen": "caneta", "ballpoint": "caneta", "bllpoint": "caneta", "inkpen": "caneta", "pulpen": "caneta", "penpencil": None,
    "sharpener": "apontador", "sharpner": "apontador", "sharpeners": "apontador", "pengserut": "apontador", "pointer": None,
    "eraser": "borracha", "rubber": "borracha", "penghapus": "borracha",
    "notebook": "caderno", "notepad": "caderno",
    "ruler": "regua", "scale": "regua", "penggaris": "regua",
    "scissor": "tesoura", "scissors": "tesoura", "sessior": "tesoura",
}
FINAIS = ["lapis", "caneta", "apontador", "borracha", "caderno", "regua", "tesoura"]
norm = lambda s: re.sub(r"[^a-z]", "", str(s).lower())
MAPA_N = {norm(k): v for k, v in MAPA.items()}
SPLITS = {"train": "train", "valid": "val", "val": "val", "test": "test"}

def main(origem, saida):
    origem, saida = Path(origem), Path(saida)
    if saida.exists(): shutil.rmtree(saida)
    cont = collections.Counter(); imgs = collections.Counter(); ignoradas = collections.Counter()
    for ds in sorted(p for p in origem.iterdir() if p.is_dir()):
        y = ds / "data.yaml"
        if not y.exists():
            print("sem data.yaml, ignorando", ds.name); continue
        nomes = yaml.safe_load(y.read_text(encoding="utf-8"))["names"]
        nomes = list(nomes.values()) if isinstance(nomes, dict) else list(nomes)
        conv = {i: MAPA_N.get(norm(n)) for i, n in enumerate(nomes)}
        for n in nomes:
            if MAPA_N.get(norm(n)) is None: ignoradas[f"{ds.name}:{n}"] += 1
        for sp_orig, sp in SPLITS.items():
            pi, pl = ds / sp_orig / "images", ds / sp_orig / "labels"
            if not pi.exists(): continue
            for img in pi.iterdir():
                lab = pl / (img.stem + ".txt")
                if not lab.exists(): continue
                linhas = []
                for l in lab.read_text().splitlines():
                    p = l.split()
                    if len(p) < 5: continue
                    f = conv.get(int(float(p[0])))
                    if f is None: continue
                    linhas.append(f"{FINAIS.index(f)} " + " ".join(p[1:]))
                    cont[f] += 1
                if not linhas: continue
                (saida / "images" / sp).mkdir(parents=True, exist_ok=True); (saida / "labels" / sp).mkdir(parents=True, exist_ok=True)
                novo = f"{ds.name}_{img.stem}"
                shutil.copy(img, saida / "images" / sp / (novo + img.suffix))
                (saida / "labels" / sp / (novo + ".txt")).write_text("\n".join(linhas) + "\n")
                imgs[sp] += 1
    if not imgs:
        raise SystemExit("Nenhuma imagem aproveitada: confira os nomes das classes (veja MAPA no topo do arquivo).")
    (saida / "data.yaml").write_text(yaml.safe_dump({"path": str(saida.resolve()), "train": "images/train", "val": "images/val" if imgs["val"] else "images/train",
                                                    "test": "images/test" if imgs["test"] else "images/val", "names": {i: n for i, n in enumerate(FINAIS)}}, allow_unicode=True), encoding="utf-8")
    print("imagens por split:", dict(imgs)); print("caixas por classe:", dict(cont))
    sem = [c for c in FINAIS if cont[c] == 0]
    if sem: print("ATENÇÃO sem nenhuma caixa:", sem, "-> baixe outro dataset com essas classes")
    if ignoradas: print("classes de origem descartadas (fora do MAPA):", sorted(ignoradas))

if __name__ == "__main__":
    if len(sys.argv) != 3: raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
