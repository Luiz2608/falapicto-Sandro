"""Guarda anti-invenção: confere se a frase do SLM é FIEL aos cards (não omite nem inventa). Usado no dataset, no benchmark e na API."""
import re, unicodedata
from core import CARDS

_N = lambda t: unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
_PALAVRAS = lambda t: re.findall(r"[a-zà-ú]+", _N(t))
# palavras que costumam ser INVENÇÃO do modelo (lugar, companhia, modo, quantidade...)
INVENCAO = {"na", "no", "nas", "nos", "para", "perto", "durante", "sentado", "sentada", "algo", "pouco", "vezes", "ver",
            "sozinho", "depois", "antes", "hoje", "agora", "porque", "mas", "tambem", "ainda", "quando", "onde", "dentro", "fora",
            "amiguinho", "amiguinha", "mamaezinha"}


def _lex():
    """palavras de CONTEÚDO de cada card (recalculado: acompanha os cards cadastrados no admin)"""
    lex = {}
    for i, c in CARDS.items():
        toks = set(_PALAVRAS(c["label"]))
        if c.get("np"): toks |= set(_PALAVRAS(c.get("bare") or c["np"])) - {"o", "a", "os", "as", "um", "uma"}
        if c.get("inf"): toks |= set(_PALAVRAS(c["inf"]))
        if c["cat"] in ("objeto", "pessoa", "sentir", "verbo") and i not in ("eu_quero", "nao_quero", "terminei", "dor"):
            lex[i] = toks - {"eu", "quero", "nao", "por", "favor", "mais", "com"}
    lex.update({"dor": {"dor", "doendo", "doem", "doi", "doer"}, "lanche": {"lanche", "lanchar"}, "comer": {"comer"}, "beber": {"beber"},
                "terminei": {"terminei"}, "ajuda": {"ajuda"}, "medo": {"medo"}, "cabeca": {"cabeca"}, "mamae": {"mamae"},
                "agua": {"agua"}, "banheiro": {"banheiro"}, "atividade": {"atividade"}})
    for k in ("mais", "por_favor", "eu_quero", "nao_quero", "sim", "nao", "oi", "tchau", "obrigado", "acabou"):
        lex.pop(k, None)
    return lex


def verificar(ids, frase):
    """None se a frase é fiel aos cards; senão o motivo do descarte."""
    ids = list(ids)
    pal = _PALAVRAS(frase)
    S = set(pal)
    lex = _lex()
    for i in ids:                                    # 1) todo conteúdo escolhido aparece
        if i in lex and not (lex[i] & S):
            return "omite um card"
    for i, toks in lex.items():                      # 2) nenhum conteúdo de card NÃO escolhido aparece
        if i not in ids and toks & S and i not in ("ajuda",):
            return "menciona card não escolhido"
    ban = set(INVENCAO)
    dorloc = "dor" in ids or any(CARDS[i].get("loc") for i in ids if i in CARDS)
    if dorloc: ban -= {"na", "no", "nas", "nos"}
    extras = S & ban
    if extras: return "invenção: " + "/".join(sorted(extras))
    if "nem" in S and "nao_quero" not in ids: return "invenção: nem"
    if "com" in S and not ({"ajuda", "medo", "brincar"} & set(ids)) and not dorloc: return "invenção: com"
    if ({"ir", "ao"} & S) and "banheiro" not in ids: return "invenção: ir ao"
    if "fazer" in S and "atividade" not in ids: return "invenção: fazer"
    if ({"de", "do", "da"} & S) and not (dorloc or "ajuda" in ids or ("agua" in ids and {"copo", "garrafa"} & set(ids))): return "invenção: de/do/da"
    return None