"""Núcleo compartilhado: vocabulário e regras de frase (camada 'rápida' do router)."""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = json.loads((ROOT / "data" / "cards.json").read_text(encoding="utf-8"))
CARDS = {c["id"]: c for c in DATA["cards"]}
ROTINAS = DATA["rotinas"]


def _np(c):
    return c.get("np") or c.get("bare") or c["label"].lower()


def _bare(c):
    if c.get("bare"):
        return c["bare"]
    if c.get("np"):   # tira o artigo: "a bola" -> "bola"
        return re.sub(r"^(o|a|os|as|um|uma)\s+", "", c["np"].strip(), flags=re.I)
    return c["label"].lower()


# Cards que "abrem" a frase. Se a criança tocar fora de ordem ("cabeça" + "dor"), a ordem é corrigida.
INICIAM = ("eu_quero", "nao_quero", "dor", "terminei", "ajuda", "oi", "tchau", "obrigado")


def ordenar(ids):
    """Põe o card que inicia a frase na frente (e 'por favor' no fim). O resto mantém a ordem do toque."""
    ids = [i for i in ids if i in CARDS]
    if "ajuda" in ids and ("eu_quero" in ids or "nao_quero" in ids):
        lider = "eu_quero" if "eu_quero" in ids else "nao_quero"
    else:
        lider = next((i for i in ids if i in INICIAM), None)
    if lider and ids[0] != lider:
        ids.remove(lider)
        ids.insert(0, lider)
    if "por_favor" in ids and ids[-1] != "por_favor":
        ids.remove("por_favor")
        ids.append("por_favor")
    return ids


def frase_dor(loc_card):
    """'Minha cabeça está doendo.' / 'Meu dente está doendo.' (concordância pelo 'na/no/nas/nos' do cadastro)."""
    loc = loc_card["loc"].strip()
    m = re.match(r"^(na|no|nas|nos)\s+(.*)$", loc, flags=re.I)
    if not m:
        return f"Estou com dor {loc}."
    art, resto = m.group(1).lower(), m.group(2)
    poss, verbo = {"na": ("Minha", "está"), "no": ("Meu", "está"), "nas": ("Minhas", "estão"), "nos": ("Meus", "estão")}[art]
    return f"{poss} {resto} {verbo} doendo."


# objetos que não são "coisas" mas ações: "Eu quero o banheiro" -> "Eu quero ir ao banheiro"
ACAO_DO_OBJETO = {"banheiro": "ir ao banheiro", "atividade": "fazer a atividade"}


def _alvo(c):
    """como o card entra depois de 'quero': 'a bola' / 'ir ao banheiro'"""
    return ACAO_DO_OBJETO.get(c["id"]) or _np(c)


def _vocativo(c):
    b = _bare(c)
    return b[:1].upper() + b[1:]


RECIPIENTES = {"copo": "um copo", "garrafa": "uma garrafa"}   # "copo" + "água" -> "um copo de água"
CONTEUDOS = {"agua"}


def _recipiente(rest):
    """Se rest = [recipiente, conteúdo] (em qualquer ordem) devolve 'um copo de água'; senão None."""
    if len(rest) == 2:
        a, b = rest
        for rec, con in ((a, b), (b, a)):
            if rec["id"] in RECIPIENTES and con["id"] in CONTEUDOS:
                return f"{RECIPIENTES[rec['id']]} de {_bare(con)}"
    return None


def rule_sentence(ids):
    """Tenta montar a frase por regras. Retorna str ou None (None => precisa do SLM)."""
    ids = ordenar(ids)
    cs = [CARDS[i] for i in ids]
    if not cs:
        return None
    first, rest = cs[0], cs[1:]
    # remove 'por favor' final (ele é tratado como educação, não conteúdo)
    polite = False
    if rest and rest[-1]["id"] == "por_favor":
        polite, rest = True, rest[:-1]
    pf = ", por favor" if polite else ""

    # cartão único com fala própria
    if not rest and first.get("spoken"):
        return first["spoken"] + ("." if not first["spoken"].endswith(("!", "?")) else "")

    if first["id"] == "eu_quero":
        if not rest:
            return "Eu quero."
        if len(rest) == 1:
            r = rest[0]
            if r["id"] == "mais":
                return "Eu quero mais" + pf + "."
            if r["id"] == "ajuda":
                return f"Eu quero ajuda{pf}."
            if r.get("inf"):
                return f"Eu quero {r['inf']}{pf}."
            if r["cat"] in ("objeto", "pessoa"):
                return f"Eu quero {_alvo(r)}{pf}."
        rec = _recipiente(rest)
        if rec:
            return f"Eu quero {rec}{pf}."
        if len(rest) == 2 and rest[0]["id"] == "mais" and rest[1]["cat"] == "objeto":
            return f"Eu quero mais {_bare(rest[1])}{pf}."
        if len(rest) == 2 and rest[1]["id"] == "mais" and rest[0]["cat"] == "objeto":
            return f"Eu quero mais {_bare(rest[0])}{pf}."
        return None

    if first["id"] == "nao_quero":
        rec = _recipiente(rest)
        if rec:
            return f"Não quero {rec}."
        if len(rest) == 1:
            r = rest[0]
            if r["id"] == "ajuda":
                return f"Não quero ajuda{pf}."
            if r.get("inf"):
                return f"Não quero {r['inf']}."
            if r["cat"] in ("objeto", "pessoa"):
                return f"Não quero {_alvo(r)}."
        return None

    if first["id"] == "dor" and rest and all(r.get("loc") or r["cat"] == "pessoa" for r in rest) and any(r.get("loc") for r in rest):
        locs = [r for r in rest if r.get("loc")]
        pess = [r for r in rest if r["cat"] == "pessoa"]
        voc = (_vocativo(pess[0]) + ", ") if pess else ""
        if len(locs) == 1:
            f = frase_dor(locs[0])
        else:   # "Minha cabeça e minha barriga estão doendo."
            partes = []
            for l in locs:
                m = re.match(r"^(na|no|nas|nos)\s+(.*)$", l["loc"].strip(), flags=re.I)
                partes.append(({"na": "minha", "no": "meu", "nas": "minhas", "nos": "meus"}[m.group(1).lower()] + " " + m.group(2)) if m else l["loc"])
            f = _juntar(partes, "e"); f = f[:1].upper() + f[1:] + " estão doendo."
        return (voc + (f[:1].lower() + f[1:] if voc else f)).replace("..", ".")
    if first["id"] == "dor" and len(rest) == 1 and rest[0].get("loc"):
        return frase_dor(rest[0])

    if first["id"] == "terminei" and len(rest) == 1 and rest[0]["cat"] == "objeto":
        return f"Terminei {_np(rest[0])}."

    if first["id"] == "ajuda" and len(rest) == 1 and rest[0]["id"] == "banheiro":
        return "Preciso de ajuda para ir ao banheiro."

    if first["id"] == "ajuda" and len(rest) == 1 and rest[0]["cat"] == "objeto":
        return f"Preciso de ajuda com {_np(rest[0])}."

    if first["id"] == "ajuda" and len(rest) == 1 and rest[0]["cat"] == "pessoa":      # fala COM a pessoa
        return f"{_vocativo(rest[0])}, preciso de ajuda."

    # sentimento + pessoa (qualquer ordem): a criança conta à pessoa como se sente
    if len(cs) == 2 and {cs[0]["cat"], cs[1]["cat"]} == {"sentir", "pessoa"}:
        sen = cs[0] if cs[0]["cat"] == "sentir" else cs[1]
        pes = cs[1] if sen is cs[0] else cs[0]
        if sen.get("spoken") and not sen.get("loc"):
            return f"{_vocativo(pes)}, {sen['spoken'][:1].lower() + sen['spoken'][1:]}."

    if first["id"] in ("oi", "tchau", "obrigado") and len(rest) == 1 and rest[0]["cat"] == "pessoa":
        saud = {"oi": "Oi", "tchau": "Tchau", "obrigado": "Obrigado"}[first["id"]]
        return f"{saud}, {_bare(rest[0])}!"

    # "Terminei" + pessoa: a criança avisa a pessoa (vocativo), não "terminei a mãe"
    if first["id"] == "terminei" and len(rest) == 1 and rest[0]["cat"] == "pessoa":
        return f"{_vocativo(rest[0])}, terminei."

    # "mais" / "acabou" + objeto, em qualquer ordem: "Mais água." / "Acabou o lanche."
    nucleo = [first] + rest
    if len(nucleo) == 2:
        ids2 = {c["id"]: c for c in nucleo}
        obj = next((c for c in nucleo if c["cat"] == "objeto"), None)
        if obj is not None and "mais" in ids2:
            return f"Mais {_bare(obj)}{pf}."
        if obj is not None and "acabou" in ids2:
            return f"Acabou {_np(obj)}{pf}."

    return None


def _juntar(partes, conj):
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + f" {conj} " + partes[-1]


def lista_sentence(ids):
    """Rede de segurança (sem IA) para listas: 'Eu quero a bola e o lápis.' / 'Não quero a bola nem o lápis.'. None se não for lista."""
    ids = ordenar(ids)
    cs = [CARDS[i] for i in ids]
    # só sentimentos: "Estou feliz e cansado." / "Estou feliz e com medo."
    if len(cs) >= 2 and all(x["cat"] == "sentir" and not x.get("loc") and x["id"] != "dor" and (x.get("spoken") or "").startswith("Estou ") for x in cs):
        return "Estou " + _juntar([x["spoken"][6:] for x in cs], "e") + "."
    if len(ids) < 3 or ids[0] not in ("eu_quero", "nao_quero"):
        return None
    pf = ""
    if ids[-1] == "por_favor":
        ids, pf = ids[:-1], ", por favor"
    itens = [CARDS[i] for i in ids[1:]]
    if len(itens) < 2 or not all(x["cat"] in ("objeto", "pessoa") or x.get("inf") for x in itens):
        return None
    partes = [x["inf"] if x.get("inf") and x["cat"] != "objeto" else _alvo(x) for x in itens]
    if ids[0] == "eu_quero":
        return f"Eu quero {_juntar(partes, 'e')}{pf}."
    return f"Não quero {_juntar(partes, 'nem')}."


def fallback_sentence(ids):
    """Último recurso (SLM fora do ar ou reprovado): nunca devolve lista crua de rótulos.
    pessoa vira vocativo, sentimentos viram 'Estou ...', o resto é juntado com 'e'."""
    cs = [CARDS[i] for i in ids if i in CARDS]
    if not cs:
        return ""
    if sum(1 for c in cs if c.get("loc")) > 1 and any(c["id"] == "dor" for c in cs):
        r = rule_sentence([c["id"] for c in cs])
        if r: return r
    pess = [c for c in cs if c["cat"] == "pessoa" and len(cs) > 1]
    resto = [c for c in cs if c not in pess and c["id"] not in ("por_favor",)]
    pf = ", por favor" if any(c["id"] == "por_favor" for c in cs) else ""
    voc = (_vocativo(pess[0]) + ", ") if pess else ""
    if any(c["id"] == "dor" for c in resto):
        locs = [c for c in resto if c.get("loc")]
        if locs:
            f = frase_dor(locs[0])
            return voc + (f[:1].lower() + f[1:] if voc else f)
    partes = []
    for c in resto:
        sp = c.get("spoken") or ""
        if c["cat"] == "sentir" and sp.startswith("Estou "):
            partes.append(sp[6:])
        else:
            partes.append(c["label"].lower())
    if all(c["cat"] == "sentir" and (c.get("spoken") or "").startswith("Estou ") for c in resto) and resto:
        txt = "estou " + _juntar(partes, "e")
    else:
        txt = _juntar(partes, "e")
    f = voc + txt if voc else txt
    return f[:1].upper() + f[1:] + pf + "."


def sentence_with_context(ids, contexto):
    """Usa a frase anterior da sessão para completar pedidos curtos: 'Mais' -> 'Eu quero mais maçã.'"""
    if list(ids) == ["mais"]:
        objs = [CARDS[i] for i in contexto if i in CARDS and CARDS[i]["cat"] == "objeto"]
        if objs:
            return f"Eu quero mais {_bare(objs[-1])}."
    return None


# ---------- cadastro (admin): recarregar e salvar sem reiniciar ----------
import os, re, shutil, tempfile

_CARDS_FILE = ROOT / "data" / "cards.json"


def reload_data():
    """Relê cards.json e atualiza DATA/CARDS/ROTINAS EM PLACE (quem importou continua enxergando)."""
    novo = json.loads(_CARDS_FILE.read_text(encoding="utf-8"))
    DATA.clear(); DATA.update(novo)
    CARDS.clear(); CARDS.update({c["id"]: c for c in DATA["cards"]})
    ROTINAS.clear(); ROTINAS.update(DATA["rotinas"])


def save_data():
    """Grava cards.json de forma atômica, com cópia de segurança."""
    if _CARDS_FILE.exists():
        shutil.copy2(_CARDS_FILE, _CARDS_FILE.with_suffix(".json.bak"))
    fd, tmp = tempfile.mkstemp(dir=_CARDS_FILE.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _CARDS_FILE)
    reload_data()


def slug(texto):
    import unicodedata
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "card"


# ---------- formato único do prompt do SLM (treino, API e benchmark usam ISTO) ----------
SYSTEM = "Você ajuda uma criança a se comunicar. Transforme os cards escolhidos em UMA frase curta, natural e correta em português do Brasil. Não invente informação que não esteja nos cards."


def cards_text(ids):
    return "Cards: " + ", ".join(CARDS[i]["label"] for i in ids if i in CARDS)


def prompt_messages(ids):
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": cards_text(ids)}]


def extrair_resposta(txt):
    """Pega a frase do texto gerado: <resposta>…</resposta>; senão, limpa <think>/<pensamento>."""
    m = re.search(r"<resposta>(.*?)</resposta>", txt, re.S)
    if m:
        return m.group(1).strip()
    txt = re.sub(r"<think>.*?</think>|<pensamento>.*?</pensamento>", "", txt, flags=re.S)
    return re.sub(r"</?resposta>", "", txt).strip()