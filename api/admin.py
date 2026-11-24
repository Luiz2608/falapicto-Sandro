"""Cadastro de cards para fonoaudiólogas e professores (protegido por PIN).
O PIN vem da variável de ambiente ADMIN_PIN (padrão '1234' — TROQUE antes de usar na escola)."""
import os, re, io, time, uuid, secrets, threading
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, File
from pydantic import BaseModel
import core
from core import DATA, CARDS, ROTINAS, ROOT, slug

router = APIRouter(prefix="/api/admin")
UPLOADS = ROOT / "data" / "uploads"
UPLOADS.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()
MAX_POR_ROTINA = 9
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def exige_pin(x_admin_pin: str = Header(default="")):
    pin = os.environ.get("ADMIN_PIN", "1234")
    if os.environ.get("FALAPICTO_PROD") and pin == "1234":
        raise HTTPException(503, "Servidor sem ADMIN_PIN configurado.")
    if not secrets.compare_digest(x_admin_pin.encode(), pin.encode()):
        time.sleep(0.6)  # atrapalha tentativas em sequência
        raise HTTPException(401, "PIN incorreto.")


class Login(BaseModel):
    pin: str


class CardIn(BaseModel):
    id: Optional[str] = None
    label: str
    cat: str
    emoji: str = ""
    img: Optional[str] = None
    cor: Optional[str] = None
    spoken: Optional[str] = None
    np: Optional[str] = None
    inf: Optional[str] = None
    rotinas: list[str] = []


class RotinaIn(BaseModel):
    cards: list[str]


@router.post("/login")
def login(b: Login):
    exige_pin(b.pin)
    return {"ok": True}


def _limpa(v):
    v = (v or "").strip()
    return v or None


@router.put("/card", dependencies=[Depends(exige_pin)])
def salvar_card(b: CardIn):
    label = b.label.strip()
    if not (1 <= len(label) <= 20):
        raise HTTPException(400, "A legenda precisa ter de 1 a 20 letras.")
    if b.cat not in DATA["categories"]:
        raise HTTPException(400, "Categoria inválida.")
    cor = _limpa(b.cor)
    if cor and not HEX.match(cor):
        raise HTTPException(400, "Cor inválida.")
    emoji, img = (b.emoji or "").strip(), _limpa(b.img)
    if not emoji and not img:
        raise HTTPException(400, "Escolha um emoji ou envie uma imagem para o ícone.")
    if len(emoji) > 12:
        raise HTTPException(400, "Use só um emoji no ícone.")
    if img and not (img.startswith("/uploads/") or img.startswith("/static/icons/")) or (img and ".." in img):
        raise HTTPException(400, "Imagem inválida.")
    np_ = _limpa(b.np)
    if b.cat in ("objeto", "pessoa") and not np_:
        raise HTTPException(400, 'Preencha "Como falar na frase" com o artigo, por exemplo: a bola.')
    spoken, inf = _limpa(b.spoken), _limpa(b.inf)
    if spoken and len(spoken) > 80:
        raise HTTPException(400, "A fala é longa demais (máximo 80 letras).")
    for r in b.rotinas:
        if r not in ROTINAS:
            raise HTTPException(400, f"Rotina desconhecida: {r}")

    with _lock:
        existente = CARDS.get(b.id) if b.id else None
        cid = existente["id"] if existente else None
        if not cid:
            base = slug(label); cid = base; n = 2
            while cid in CARDS:
                cid = f"{base}_{n}"; n += 1
        # limite de 9 por rotina (grade 3x3)
        for r in b.rotinas:
            if cid not in ROTINAS[r]["cards"] and len(ROTINAS[r]["cards"]) >= MAX_POR_ROTINA:
                raise HTTPException(400, f'A rotina "{ROTINAS[r]["nome"]}" já tem {MAX_POR_ROTINA} cards. Tire um antes.')
        card = existente if existente else {"id": cid}
        antiga_img = card.get("img")
        card.update({"label": label, "cat": b.cat, "emoji": emoji})
        for k, v in (("cor", cor), ("img", img), ("spoken", spoken), ("np", np_), ("inf", inf)):
            if v: card[k] = v
            else: card.pop(k, None)
        if np_: card["bare"] = core._bare({"np": np_, "label": label})
        else: card.pop("bare", None)
        if not existente:
            DATA["cards"].append(card)
        for rid, r in ROTINAS.items():
            if rid in b.rotinas and cid not in r["cards"]:
                r["cards"].append(cid)
            elif rid not in b.rotinas and cid in r["cards"]:
                r["cards"].remove(cid)
        core.save_data()
        if antiga_img and antiga_img != img and antiga_img.startswith("/uploads/"):
            (UPLOADS / Path(antiga_img).name).unlink(missing_ok=True)
    return CARDS[cid]


@router.delete("/card/{cid}", dependencies=[Depends(exige_pin)])
def apagar_card(cid: str):
    with _lock:
        if cid not in CARDS:
            raise HTTPException(404, "Card não existe.")
        img = CARDS[cid].get("img")
        DATA["cards"] = [c for c in DATA["cards"] if c["id"] != cid]
        for r in DATA["rotinas"].values():
            if cid in r["cards"]: r["cards"].remove(cid)
        DATA["sempre_visiveis"] = [x for x in DATA["sempre_visiveis"] if x != cid]
        DATA["objetos_coco"] = {k: v for k, v in DATA["objetos_coco"].items() if v != cid}
        core.save_data()
        if img and img.startswith("/uploads/"):
            (UPLOADS / Path(img).name).unlink(missing_ok=True)
    return {"ok": True}


@router.put("/rotina/{rid}", dependencies=[Depends(exige_pin)])
def ordenar_rotina(rid: str, b: RotinaIn):
    if rid not in ROTINAS:
        raise HTTPException(404, "Rotina não existe.")
    if len(b.cards) != len(set(b.cards)):
        raise HTTPException(400, "Card repetido na rotina.")
    if len(b.cards) > MAX_POR_ROTINA:
        raise HTTPException(400, f"No máximo {MAX_POR_ROTINA} cards por rotina.")
    if any(c not in CARDS for c in b.cards):
        raise HTTPException(400, "Card desconhecido.")
    with _lock:
        ROTINAS[rid]["cards"] = list(b.cards)
        core.save_data()
    return {"ok": True}


@router.post("/upload", dependencies=[Depends(exige_pin)])
async def upload(file: UploadFile = File(...)):
    from PIL import Image
    raw = await file.read()
    if len(raw) > 3_000_000:
        raise HTTPException(400, "Imagem grande demais (máximo 3 MB).")
    try:
        im = Image.open(io.BytesIO(raw)); im.verify()
        im = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        raise HTTPException(400, "Esse arquivo não é uma imagem válida.")
    im.thumbnail((256, 256))
    nome = f"{uuid.uuid4().hex[:12]}.png"
    im.save(UPLOADS / nome, "PNG")
    return {"url": f"/uploads/{nome}"}
