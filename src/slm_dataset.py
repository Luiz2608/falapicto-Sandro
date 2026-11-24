"""Dataset do SLM (destilação): cards -> frase.  Formato ShareGPT igual ao dataset da aula
(<pensamento>/<resposta>).  Três subcomandos:
  semente : gera pares corretos a partir das REGRAS (dados semente, 100% confiáveis)
  prompt  : imprime o prompt para o LLM PROFESSOR (Gemini Pro) gerar combinações novas
  combos  : gera N combinações plausíveis de cards (com semente aleatória) e imprime o prompt PRONTO para o professor
            rotular. Rode várias vezes com sementes diferentes:  python slm_dataset.py combos 120 1   (depois 2, 3...)
  curar   : filtra a saída do(s) professor(es) (dedupe, recusas, PII, cards desconhecidos, tamanho) e junta com a semente.
            Aceita linhas  "Cards: A, B, C => Frase."  ou JSONL.   python slm_dataset.py curar lote1.txt lote2.txt ...
"""
import sys, json, re, random, collections
from core import ROOT, CARDS, rule_sentence, SYSTEM, cards_text, ordenar
OUT = ROOT / "data"


def row(ids, frase, pens=None):
    labels = ", ".join(CARDS[i]["label"] for i in ids)
    pens = pens or f"Cards: {labels}. Monto uma frase curta em primeira pessoa, sem acrescentar nada além dos cards."
    return {"conversations": [
        {"from": "system", "value": SYSTEM},
        {"from": "human", "value": cards_text(ids)},
        {"from": "gpt", "value": f"<pensamento>{pens}</pensamento>\n<resposta>{frase}</resposta>"}]}


def semente():
    seen, rows = set(), []
    for l in open(OUT / "seqs.jsonl", encoding="utf-8"):
        seq = tuple(json.loads(l)["seq"])
        if seq in seen:
            continue
        seen.add(seq)
        f = rule_sentence(list(seq))
        if f:
            rows.append(row(list(seq), f))
    # + combinações que as regras sabem montar (gramática garantida, sem alucinação)
    for seq in gerar_combos(4000, 0):
        f = rule_sentence(seq)
        if f and tuple(seq) not in seen:
            seen.add(tuple(seq)); rows.append(row(seq, f))
    (OUT / "slm_semente.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    print(f"semente: {len(rows)} pares únicos")


def prompt(n=300):
    vocab = "\n".join(f"- {c['label']}" for c in CARDS.values())
    ex = [row(["eu_quero", "mais", "agua"], "Eu quero mais água."), row(["dor", "barriga"], "Estou com dor na barriga.")]
    exs = "\n".join(json.dumps(e, ensure_ascii=False) for e in ex)
    print(f"""Você é o PROFESSOR de um modelo pequeno (SLM) que ajuda crianças com dificuldade de fala a se comunicar na escola.
A criança toca em 2 a 4 cards (figuras) e o modelo precisa devolver UMA frase curta (até 12 palavras), natural, em português do Brasil, na 1ª pessoa.

REGRAS:
- Use SOMENTE os cards escolhidos. NÃO invente informação (não crie sintomas, pedidos ou pessoas que não estão nos cards).
- Se a combinação não faz sentido, devolva a frase mais simples e segura possível com os cards, sem inventar.
- Varie a combinação de cards: misture verbos, objetos, pessoas e sentimentos, inclusive combinações incomuns.
- Sem nomes reais, telefones ou dados pessoais.

CARDS DISPONÍVEIS:
{vocab}

FORMATO: gere {n} linhas JSONL (uma por linha, sem texto extra), exatamente neste formato:
{exs}

Gere {n} linhas agora.""")


def gerar_combos(n, seed):
    """Combinações plausíveis que a criança pode formar (ordem canônica). Cobre tudo que as regras NÃO cobrem."""
    rnd = random.Random(seed)
    g = lambda f: [i for i, c in CARDS.items() if f(c)]
    objs, pess = g(lambda c: c["cat"] == "objeto"), g(lambda c: c["cat"] == "pessoa")
    infs = g(lambda c: c.get("inf"))
    locs = g(lambda c: c.get("loc"))
    sent = g(lambda c: c["cat"] == "sentir" and not c.get("loc") and c["id"] != "dor")
    has = lambda *ids: all(i in CARDS for i in ids)
    gens = []
    if has("eu_quero"):
        gens += [(5, lambda: ["eu_quero", rnd.choice(objs)]), (6, lambda: ["eu_quero"] + rnd.sample(objs, 2)),
                 (3, lambda: ["eu_quero", rnd.choice(infs)] if infs else None),
                 (3, lambda: ["eu_quero", rnd.choice(infs), rnd.choice(objs)] if infs else None),
                 (3, lambda: ["eu_quero", "mais", rnd.choice(objs)] if has("mais") else None),
                 (3, lambda: ["eu_quero"] + rnd.sample(objs, 2) + ["por_favor"] if has("por_favor") else None),
                 (2, lambda: ["eu_quero", rnd.choice(pess)] if pess else None)]
    if has("nao_quero"):
        gens += [(3, lambda: ["nao_quero", rnd.choice(objs + infs)]), (2, lambda: ["nao_quero"] + rnd.sample(objs, 2))]
    if has("dor") and locs:
        gens += [(3, lambda: ["dor", rnd.choice(locs)]), (1, lambda: ["dor"] + rnd.sample(locs, min(2, len(locs))))]
    if has("ajuda"):
        gens += [(3, lambda: ["ajuda", rnd.choice(objs)]), (1, lambda: ["ajuda", rnd.choice(pess)] if pess else None)]
    if has("terminei"):
        gens += [(2, lambda: ["terminei", rnd.choice(objs)])]
    for sd in ("oi", "tchau", "obrigado"):
        if has(sd) and pess:
            gens += [(1, lambda sd=sd: [sd, rnd.choice(pess)])]
    if sent and pess:
        gens += [(2, lambda: [rnd.choice(sent), rnd.choice(pess)]), (2, lambda: [rnd.choice(pess), rnd.choice(sent)])]
    if sent:
        gens += [(2, lambda: [rnd.choice(sent)] + rnd.sample(sent, 1))]
    fixos = [["eu_quero", "copo", "agua"], ["eu_quero", "garrafa", "agua"], ["eu_quero", "agua"]]
    vistos, out = set(), []
    for f in fixos:
        if all(i in CARDS for i in f) and seed == 1:   # só no 1º lote: os pedidos mais comuns
            out.append(f); vistos.add(tuple(f))
    pesos = [w for w, _ in gens]
    tent = 0
    while len(out) < n and tent < n * 40:
        tent += 1
        seq = rnd.choices(gens, weights=pesos)[0][1]()
        if not seq or len(set(seq)) != len(seq):
            continue
        seq = ordenar(seq)
        if tuple(seq) not in vistos:
            vistos.add(tuple(seq)); out.append(seq)
    return out


def combos(n=120, seed=1):
    lista = [q for q in gerar_combos(int(n) * 3, int(seed)) if not rule_sentence(q)][:int(n)]
    linhas = "\n".join(cards_text(s) for s in lista)
    print(f"""Você é o PROFESSOR de um modelo pequeno que ajuda crianças com dificuldade de fala (comunicação alternativa) na escola.
Abaixo há {len(lista)} combinações de cards que a criança tocou, em ordem. Para CADA uma, escreva UMA frase curta (até 12 palavras),
natural, correta, em português do Brasil, na 1ª pessoa, como a criança falaria.

REGRAS:
- Use apenas o que está nos cards. Não invente sintomas, pedidos, pessoas ou lugares.
- Conserte a gramática: artigos (um/uma/o/a), preposições ("um copo DE água", "dor NA barriga", "preciso DE ajuda"), concordância.
- "Eu quero" + copo + água => "Eu quero um copo de água."   |   dor + cabeça => "Minha cabeça está doendo."   |   dor + barriga => "Minha barriga está doendo."
- Se a combinação for estranha, devolva a frase mais simples e segura possível com os cards, sem inventar nada.
- Sem nomes reais, telefones ou dados pessoais. Sem explicações, sem numeração, sem markdown.

FORMATO: uma linha por combinação, EXATAMENTE assim (repita o texto "Cards: ..." idêntico ao que recebeu, depois " => " e a frase):
Cards: Eu quero, Copo, Água => Eu quero um copo de água.
Cards: Dor, Cabeça => Minha cabeça está doendo.

COMBINAÇÕES:
{linhas}
""")


from guarda import verificar, _PALAVRAS, _N  # noqa: E402


RECUSA = re.compile(r"como um (modelo|assistente)|não posso|desculp|não consigo", re.I)
PII = re.compile(r"\b\d{2}[\s-]?\d{4,5}[\s-]?\d{4}\b|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|@\w+\.\w+")
LABEL2ID = {c["label"].lower(): i for i, c in CARDS.items()}


def _linhas_professor(arqs):
    """Converte linhas 'Cards: A, B => Frase.' em linhas JSONL (ShareGPT); linhas JSONL passam direto."""
    for arq in arqs:
        for l in open(arq, encoding="utf-8"):
            l = l.strip()
            m = re.match(r"^(Cards:.*?)\s*=>\s*(.+)$", l)
            if m:
                labels = [x.strip().lower() for x in m.group(1).replace("Cards:", "").split(",")]
                ids = [LABEL2ID[x] for x in labels if x in LABEL2ID]
                if len(ids) == len(labels):
                    yield json.dumps(row(ids, m.group(2).strip().strip('"')), ensure_ascii=False)
                else:
                    yield "{ruim"   # card desconhecido -> contabilizado como inválido
            else:
                yield l


def curar(arqs):
    base = [json.loads(l) for l in open(OUT / "slm_semente.jsonl", encoding="utf-8")]
    stats = collections.Counter()
    vistos = collections.Counter()
    novos = []
    for l in _linhas_professor(arqs):
        l = l.strip()
        if not l:
            continue
        try:
            r = json.loads(l); h = r["conversations"][1]["value"]; g = r["conversations"][2]["value"]
            m = re.search(r"<resposta>(.*?)</resposta>", g, re.S); frase = m.group(1).strip()
        except Exception:
            stats["json/formato inválido"] += 1; continue
        labels = [x.strip().lower() for x in h.replace("Cards:", "").split(",")]
        if any(x not in LABEL2ID for x in labels):
            stats["card desconhecido"] += 1; continue
        ids = ordenar([LABEL2ID[x] for x in labels])
        if rule_sentence(ids):
            stats["já coberto por regra (professor ignorado)"] += 1; continue
        motivo = verificar(ids, frase)
        if motivo:
            stats["reprovado: " + motivo] += 1; continue
        r = row(ids, frase)
        if RECUSA.search(frase) or PII.search(frase):
            stats["recusa/PII"] += 1; continue
        if not (1 <= len(frase.split()) <= 12):
            stats["tamanho"] += 1; continue
        chave = tuple(ids)
        if vistos[chave] >= 1:
            stats["duplicado/conflitante"] += 1; continue
        vistos[chave] += 1
        novos.append(r)
    final = base + novos
    random.Random(1).shuffle(final)
    (OUT / "slm_train.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in final), encoding="utf-8")
    # versão CURTA (mesma ordem => mesma divisão treino/teste): o modelo responde só <resposta>, sem o bloco <pensamento>
    def curto(r):
        f = re.search(r"<resposta>(.*?)</resposta>", r["conversations"][2]["value"], re.S).group(1)
        return {"conversations": r["conversations"][:2] + [{"from": "gpt", "value": f"<resposta>{f}</resposta>"}]}
    (OUT / "slm_train_curto.jsonl").write_text("\n".join(json.dumps(curto(r), ensure_ascii=False) for r in final), encoding="utf-8")
    print(f"semente={len(base)} professor_aceitos={len(novos)} -> slm_train.jsonl ({len(final)} exemplos)")
    print("descartados/ignorados:")
    for k, v in stats.most_common():
        print(f"  {v:4d}  {k}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "semente"
    {"semente": semente, "prompt": prompt, "curar": lambda: curar(sys.argv[2:]), "combos": lambda: combos(*sys.argv[2:4])}[cmd]()
