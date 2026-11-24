"""Compositor: monta frase coerente para QUALQUER quantidade de cards, por papéis gramaticais (sem lista de combinações).
Retorna None quando a combinação é ambígua ou sem sentido -> aí o SLM decide."""
import re
from core import CARDS, ACAO_DO_OBJETO, _np, _bare, _vocativo, _juntar, _recipiente, ordenar

SAUD = {"oi": "Oi", "obrigado": "Obrigado", "tchau": "Tchau"}
# o que cada verbo aceita como complemento (id do objeto -> trecho). None = verbo sem complemento aceito
COMPL = {
    "comer": {"lanche": "o lanche", "maca": "a maçã", "banana": "a banana"},
    "beber": {"agua": "água", "copo": "no copo", "garrafa": "da garrafa"},
    "brincar": {"bola": "com a bola", "ursinho": "com o ursinho", "amigo": "com o amigo"},
    "desenhar": {"caderno": "no caderno", "lapis": "com o lápis"},
}
LOC_ART = {"na": "minha", "no": "meu", "nas": "minhas", "nos": "meus"}


def _alvo(c):
    return ACAO_DO_OBJETO.get(c["id"]) or _np(c)


def _dor(dor, locs):
    if not locs:
        return "estou com dor"
    partes = []
    for l in locs:
        m = re.match(r"^(na|no|nas|nos)\s+(.*)$", l["loc"].strip(), flags=re.I)
        partes.append(f"{LOC_ART[m.group(1).lower()]} {m.group(2)}" if m else l["loc"])
    plural = len(locs) > 1 or locs[0]["loc"].lower().startswith(("nas", "nos"))
    return _juntar(partes, "e") + (" estão doendo" if plural else " está doendo")


def _inf_frase(inf_id, objs):
    """'comer o lanche' / 'beber um copo de água'. objs = cards objeto consumidos. None se incompatível."""
    c = CARDS[inf_id]
    if not objs:
        return c["inf"]
    rec = _recipiente(objs) if inf_id == "beber" else None
    if rec:
        return f"beber {rec}"
    tab = COMPL.get(inf_id)
    if tab is None:
        return None
    partes = []
    for o in objs:
        if o["id"] not in tab:
            return None
        partes.append(tab[o["id"]])
    if inf_id == "brincar" or inf_id == "desenhar" or inf_id == "beber" and any(o["id"] in ("copo", "garrafa") for o in objs):
        return c["inf"] + " " + _juntar(partes, "e")
    return c["inf"] + " " + _juntar(partes, "e")


def _low(s):
    return s[:1].lower() + s[1:]


def _up(s):
    return s[:1].upper() + s[1:]


def compor(ids):
    ids = ordenar(ids)
    cs = [CARDS[i] for i in ids if i in CARDS]
    if not cs:
        return None
    I = [c["id"] for c in cs]
    cat = lambda k: [c for c in cs if c["cat"] == k]
    pess, objs = cat("pessoa"), list(cat("objeto"))
    sent = [c for c in cat("sentir") if c["id"] != "dor" and not c.get("loc")]
    dor = "dor" in I
    locs = [c for c in cs if c.get("loc")]
    infs = [c for c in cs if c.get("inf")]
    saud = [i for i in ("oi", "obrigado", "tchau") if i in I]
    polite = "por_favor" in I
    sim, nao = "sim" in I, "nao" in I
    eq, nq, term, ajuda, mais, acabou = (x in I for x in ("eu_quero", "nao_quero", "terminei", "ajuda", "mais", "acabou"))
    conhecidos = set(I) <= {c["id"] for c in cs}
    # cards fora da gramática conhecida => deixa pro SLM
    for c in cs:
        k = c["cat"]
        if k not in ("verbo", "social", "resposta", "pessoa", "sentir", "objeto"):
            return None
        if k == "verbo" and c["id"] not in ("eu_quero", "nao_quero", "terminei") and not c.get("inf"):
            return None
    if sim and nao or (eq and nq) or (mais and acabou) or len(saud) > 1 and set(saud) != {"obrigado", "tchau"}:
        return None
    pred = [x for x in (eq, nq, term, ajuda, acabou) if x]
    quero_ajuda = ajuda and (eq or nq) and not (term or acabou)
    if len(pred) > 1 and not quero_ajuda:
        return None

    # ---- 1) quem recebe a fala (vocativo) ----
    as_alvo = False      # pessoa como objeto de "quero" ("Eu quero a mamãe")
    if pess and (eq or nq) and not objs and not infs and not mais and not ajuda:
        as_alvo = True
    companhia = []       # 'brincar' + amigo -> "brincar com o amigo"
    if pess and infs and any(c["id"] == "brincar" for c in infs) and not saud:
        amigos = [p for p in pess if p["id"] == "amigo"]
        if amigos and len(pess) == 1 and len(infs) == 1:
            companhia = amigos
    voc_pess = [] if as_alvo or companhia else pess
    voc = (_juntar([_vocativo(p) if i == 0 else _bare(p) for i, p in enumerate(voc_pess)], "e")) if voc_pess else ""

    # ---- 2) o que é pedido ----
    consumidos = set()
    pedido = None      # (texto)
    queroinf = None
    itens_obj = [o for o in objs]
    all_inf_ids = [c["id"] for c in infs]

    def partes_obj(lst):
        lst = sorted(lst, key=lambda o: o["id"] in ACAO_DO_OBJETO)      # coisas antes de ações: "água e ir ao banheiro"
        return [_alvo(o) for o in lst]

    if (eq or nq) and not ajuda:
        neg = nq
        v = "Não quero" if neg else "Eu quero"
        conj = "nem" if neg else "e"
        extras = []
        if as_alvo:
            extras = [_np(p) for p in pess]
        elif infs:
            if len(infs) == 1:
                f = _inf_frase(infs[0]["id"], itens_obj + companhia)
                if f is None:
                    return None
                extras = [f]
                itens_obj = []
            else:
                if itens_obj:
                    return None
                extras = [c["inf"] for c in infs]
                if companhia:
                    return None
        elif companhia:
            extras = []
        elif mais:
            if not itens_obj:
                extras = ["mais"]
            else:
                rec = _recipiente(itens_obj)
                extras = ["mais " + _juntar([_bare(o) for o in itens_obj], conj)]
            itens_obj = []
        if itens_obj and not infs:
            rec = _recipiente(itens_obj)
            extras = [rec] if rec else partes_obj(itens_obj)
        elif companhia and not infs:
            return None
        txt = v + (" " + _juntar(extras, conj) if extras else "")
        if neg is False and not extras:
            return None            # "Eu quero." sozinho já tem regra; com outros cards fica sem sentido
        if neg and not extras:
            return None
        pedido = txt
        if polite: pedido += ", por favor"
    elif term:
        if infs:
            f = _inf_frase(infs[0]["id"], itens_obj + companhia) if len(infs) == 1 else _juntar([c["inf"] for c in infs], "e")
            if f is None or (len(infs) > 1 and itens_obj):
                return None
            pedido = "Terminei de " + f
        elif itens_obj:
            pedido = "Terminei " + _juntar([("no banheiro" if o["id"] == "banheiro" else _np(o)) for o in itens_obj], "e")
        else:
            pedido = "Terminei"
        if polite: return None
    elif ajuda:
        if quero_ajuda:
            base = ("Não quero mais ajuda" if nq else "Eu quero mais ajuda") if mais else ("Não quero ajuda" if nq else "Eu quero ajuda")
        else:
            if mais:
                return None
            base = "Preciso de ajuda"
        if infs:
            f = _inf_frase(infs[0]["id"], itens_obj + companhia) if len(infs) == 1 else _juntar([c["inf"] for c in infs], "e")
            if f is None or (len(infs) > 1 and itens_obj):
                return None
            pedido = f"{base} para {f}"
        elif itens_obj:
            ban = [o for o in itens_obj if o["id"] == "banheiro"]
            if ban and len(itens_obj) > 1:
                return None
            pedido = f"{base} para ir ao banheiro" if ban else f"{base} com " + _juntar([_np(o) for o in itens_obj], "e")
        else:
            pedido = base
        if polite: pedido += ", por favor"
    elif acabou:
        if not itens_obj or infs:
            return None
        pedido = "Acabou " + _juntar([_np(o) for o in itens_obj], "e")
        if polite: return None
    else:
        # sem verbo de pedido
        if infs:
            if len(infs) == 1:
                f = _inf_frase(infs[0]["id"], itens_obj + companhia)
                if f is None: return None
                pedido = "Eu quero " + f
            else:
                if itens_obj: return None
                pedido = "Eu quero " + _juntar([c["inf"] for c in infs], "e")
            if polite: pedido += ", por favor"
        elif mais:
            if not itens_obj:
                return None if len(cs) > 1 else "Mais"
            pedido = "Mais " + _juntar([_bare(o) for o in itens_obj], "e")
            if polite: pedido += ", por favor"
        elif itens_obj:
            ban = [o for o in itens_obj if o["id"] == "banheiro"]
            if (dor or locs) and ban and len(itens_obj) == 1:
                pedido = None            # banheiro entra no grupo de estado ("...doendo e preciso ir ao banheiro")
            elif ban and len(itens_obj) == 1:
                pedido = "Preciso ir ao banheiro" + (", por favor" if polite else "")
            else:
                rec = _recipiente(itens_obj)
                pedido = "Eu quero " + (rec or _juntar(partes_obj(itens_obj), "e"))
                if polite: pedido += ", por favor"
        elif polite and not (dor or locs or sent or saud):
            return None
    if polite and pedido is None and not (eq or nq or ajuda):
        # por favor sem pedido ("estou triste, por favor") não faz sentido
        if not any(o["id"] == "banheiro" for o in objs):
            return None

    # ---- 3) estado (sentimentos, dor) ----
    estado = []
    if sent:
        estado.append("estou " + _juntar([c["spoken"][6:] if (c.get("spoken") or "").startswith("Estou ") else c["label"].lower() for c in sent], "e"))
    if dor or locs:
        estado.append(_dor(next((c for c in cs if c["id"] == "dor"), None), locs))
        if any(o["id"] == "banheiro" for o in objs) and pedido is None:
            estado.append("preciso ir ao banheiro" + (", por favor" if polite else ""))
    # estado "dor/sentir" sem nada além disso é tratado aqui; verbos soltos de objetos já foram consumidos

    sentencas = []
    resposta = "Sim" if sim else ("Não" if nao else "")
    if saud:
        s = "Obrigado, tchau" if len(saud) == 2 else SAUD[saud[0]]
        s += (", " + _low(voc) if voc else "") + "!"
        sentencas.append(s); voc = ""
    if estado:
        sentencas.append(_juntar(estado, "e"))
    if pedido:
        sentencas.append(pedido)
    if not sentencas:
        if resposta and voc: return f"{resposta}, {_low(voc)}."
        if resposta: return resposta + "."
        if voc: return voc + "."
        return None
    # vocativo e resposta entram na primeira sentença (que não seja a saudação)
    i0 = 1 if saud and len(sentencas) > 1 else 0
    if saud and len(sentencas) == 1:
        if resposta: sentencas[0] = f"{resposta}, " + _low(sentencas[0])
        return sentencas[0]
    prefixo = ""
    if resposta: prefixo += resposta + ", "
    if voc: prefixo += _low(voc) + ", " if resposta else voc + ", "
    s0 = sentencas[i0]
    sentencas[i0] = _up(prefixo + _low(s0)) if prefixo else _up(s0)
    # sentenças terminam em ponto (a saudação já termina em "!")
    out = []
    for s in sentencas:
        out.append(s if s.endswith(("!", "?", ".")) else s + ".")
    return " ".join(out)