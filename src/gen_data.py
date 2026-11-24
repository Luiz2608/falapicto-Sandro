"""Gera sequências SINTÉTICAS de cards por rotina escolar (sem dados reais de crianças).
Depois da entrevista, ajuste GRAMATICA/pesos. Opcional: pedir a um LLM professor (Gemini) mais variações.
Saída: data/seqs.jsonl, data/ngram.json
"""
import json, random, collections
from core import ROOT, DATA, ROTINAS, CARDS

random.seed(42)
OBJ_LANCHE = ["lanche", "agua", "copo", "maca", "banana"]
OBJ_ATIV = ["lapis", "caderno", "livro", "tesoura"]
OBJ_BRINC = ["bola", "ursinho"]
PESSOAS = ["professora", "amigo", "mamae"]
SENT = ["feliz", "triste", "cansado", "bravo", "medo"]

# (rotina, peso, padrão). Itens com '@' são sorteados de uma lista; '?x' = opcional.
GRAMATICA = {
    "chegada": [
        (5, ["oi", "@PESSOAS"]), (2, ["oi", "@PESSOAS", "@SENT"]),
        (2, ["oi"]), (1, ["@SENT"]),
    ],
    "atividade": [
        (5, ["eu_quero", "@OBJ_ATIV"]), (2, ["eu_quero", "@OBJ_ATIV", "por_favor"]),
        (3, ["terminei", "atividade"]), (2, ["terminei"]),
        (3, ["ajuda", "@OBJ_ATIV"]), (2, ["ajuda"]), (2, ["nao_quero", "atividade"]),
        (1, ["eu_quero", "desenhar"]),
    ],
    "lanche": [
        (6, ["eu_quero", "@OBJ_LANCHE"]), (3, ["eu_quero", "@OBJ_LANCHE", "por_favor"]),
        (3, ["eu_quero", "mais", "@OBJ_LANCHE"]), (2, ["eu_quero", "mais"]),
        (2, ["acabou"]), (2, ["nao_quero", "@OBJ_LANCHE"]), (1, ["eu_quero", "comer"]), (1, ["eu_quero", "beber"]),
        (1, ["obrigado"]),
    ],
    "banheiro": [
        (6, ["banheiro"]), (3, ["dor", "barriga"]), (2, ["dor", "cabeca"]),
        (2, ["ajuda"]), (2, ["terminei"]), (1, ["obrigado"]),
    ],
    "brincar": [
        (5, ["eu_quero", "@OBJ_BRINC"]), (3, ["eu_quero", "brincar"]), (2, ["eu_quero", "@OBJ_BRINC", "por_favor"]),
        (2, ["eu_quero", "mais"]), (2, ["acabou"]), (2, ["nao_quero", "brincar"]), (1, ["@SENT"]),
    ],
    "sentimentos": [
        (4, ["@SENT"]), (3, ["dor", "barriga"]), (2, ["dor", "cabeca"]), (2, ["dor"]), (2, ["ajuda"]),
    ],
    "saida": [
        (5, ["tchau", "@PESSOAS"]), (3, ["tchau"]), (2, ["obrigado"]), (1, ["terminei"]),
    ],
}
LISTAS = {"@OBJ_LANCHE": OBJ_LANCHE, "@OBJ_ATIV": OBJ_ATIV, "@OBJ_BRINC": OBJ_BRINC, "@PESSOAS": PESSOAS, "@SENT": SENT}


FILLER = ["por_favor", "obrigado", "sim", "feliz"]


def sample(rotina, ruido=0.08, v2=False):
    # v2: a criança pede X, (às vezes) fala outras coisas, e depois pede "mais" -> o próximo card volta a ser X.
    # Dependência de LONGO ALCANCE (distância variável 2..4) que um modelo com janela curta não enxerga.
    if v2 and rotina in ("lanche", "brincar") and random.random() < 0.5:
        x = random.choice(OBJ_LANCHE if rotina == "lanche" else OBJ_BRINC)
        seq = ["eu_quero", x] + random.sample(FILLER, random.choice([0, 1, 2])) + ["mais", x]
        return seq
    pesos, pads = zip(*GRAMATICA[rotina])
    pad = random.choices(pads, weights=pesos)[0]
    seq = [random.choice(LISTAS[t]) if t.startswith("@") else t for t in pad]
    # ruído: criança às vezes toca num card "errado" da prancha
    if random.random() < ruido and len(seq) > 1:
        i = random.randrange(len(seq))
        seq[i] = random.choice(ROTINAS[rotina]["cards"])
    return seq


def main(n=20000, v2=False):
    rot = list(ROTINAS)
    rows = []
    for _ in range(n):
        r = random.choice(rot)
        rows.append({"rotina": r, "seq": sample(r, v2=v2)})
    nome = "seqs_v2.jsonl" if v2 else "seqs.jsonl"
    with open(ROOT / "data" / nome, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if v2:
        print(f"{len(rows)} sequências v2 -> data/{nome}"); return
    # baseline N-gram (bigrama condicionado à rotina) — também usado como fallback na API sem torch
    cnt = collections.defaultdict(collections.Counter)
    for r in rows:
        prev = "<s>"
        for t in r["seq"]:
            cnt[f"{r['rotina']}|{prev}"][t] += 1
            prev = t
    ngram = {k: [t for t, _ in c.most_common(6)] for k, c in cnt.items()}
    (ROOT / "data" / "ngram.json").write_text(json.dumps(ngram, ensure_ascii=False), encoding="utf-8")
    print(f"{len(rows)} sequências, {len(ngram)} contextos")


if __name__ == "__main__":
    import sys
    main(v2="--v2" in sys.argv)
