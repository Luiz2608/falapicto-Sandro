"""FalaPicto API — roda local (sem internet).
  GET  /               -> app web (web/index.html)
  GET  /api/config     -> cards, categorias, rotinas
  POST /api/next       -> próximos cards prováveis (LSTM se disponível; senão N-gram)
  POST /api/speak      -> frase final. ROUTER: regra (rápido) -> SLM (se SLM_URL) -> fallback
  POST /api/detect     -> objeto na foto (YOLO) -> card correspondente
"""
import os, sys, io, json, time, re
from pathlib import Path
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from core import DATA, CARDS, ROTINAS, ordenar, rule_sentence, lista_sentence, fallback_sentence, sentence_with_context, prompt_messages, extrair_resposta  # noqa: E402

app = FastAPI(title="FalaPicto")

from guarda import verificar  # noqa: E402
from compor import compor  # noqa: E402
from api.admin import router as admin_router  # noqa: E402
app.include_router(admin_router)


@app.on_event("startup")
def aquecer():
    if os.environ.get("SLM_URL"):          # a 1ª chamada ao SLM é a mais lenta: faz uma de mentira
        try:
            slm_sentence(["eu_quero", "bola", "lanche"])
        except Exception as e:
            print("aquecimento do SLM falhou (ok se ele ainda está iniciando):", str(e)[:100])
    """carrega o LSTM antes da primeira criança tocar (evita 1s de atraso no 1º toque)"""
    _load_lstm()
    _load_yolo()
    if _yolo["model"] is not None:   # 1ª inferência é lenta (~4 s): faz uma de mentira agora
        try:
            from PIL import Image
            _yolo["model"](Image.new("RGB", (320, 240)), verbose=False)
        except Exception as e:
            print("aquecimento YOLO falhou:", e)


# ---------- próximo card ----------
NGRAM = json.loads((ROOT / "data" / "ngram.json").read_text(encoding="utf-8")) if (ROOT / "data" / "ngram.json").exists() else {}
_lstm = {"ready": False, "model": None}


def _load_lstm():
    """Carrega o LSTM treinado (mesma arquitetura de src/train_seq.py). Opcional."""
    if _lstm["ready"]:
        return _lstm["model"]
    _lstm["ready"] = True
    ck = ROOT / "models" / "lstm.pt"
    try:
        import torch, torch.nn as nn
        if not ck.exists():
            return None
        d = torch.load(ck, map_location="cpu")
        card_ids, rot_ids = d["card_ids"], d["rot_ids"]
        off = 2
        v_in, n_out = off + len(card_ids) + len(rot_ids), off + len(card_ids)

        class Rec(nn.Module):
            def __init__(s, emb=32, hid=64):
                super().__init__()
                s.e = nn.Embedding(v_in, emb); s.r = nn.LSTM(emb, hid, batch_first=True); s.o = nn.Linear(hid, n_out)
            def forward(s, x):
                h, _ = s.r(s.e(x)); return s.o(h)

        m = Rec(); m.load_state_dict(d["state"]); m.eval()
        _lstm["model"] = (m, card_ids, rot_ids, off, torch)
    except Exception as e:  # sem torch => N-gram
        print("LSTM indisponível, usando N-gram:", e)
    return _lstm["model"]


def predict_next(rotina, seq, k=5):
    lm = _load_lstm()
    if lm:
        m, card_ids, rot_ids, off, torch = lm
        if rotina in rot_ids:
            ids = [off + len(card_ids) + rot_ids.index(rotina)] + [off + card_ids.index(c) for c in seq if c in card_ids]
            with torch.no_grad():
                lg = m(torch.tensor([ids]))[0, -1]
            lg[:off] = -1e9
            top = lg.topk(k).indices.tolist()
            return [card_ids[i - off] for i in top], "lstm"
    prev = seq[-1] if seq else "<s>"
    return NGRAM.get(f"{rotina}|{prev}", [])[:k], "ngram"


# ---------- SLM (opcional) ----------
SLM_URL = os.environ.get("SLM_URL")  # ex.: http://localhost:8080/v1/chat/completions (llama.cpp server)


def slm_sentence(seq):
    """Mesmo prompt do treino (core.prompt_messages). max_tokens cobre <pensamento>+<resposta>."""
    import httpx
    r = httpx.post(SLM_URL, json={"messages": prompt_messages(seq), "max_tokens": 128, "temperature": 0.0}, timeout=8.0)
    return extrair_resposta(r.json()["choices"][0]["message"]["content"])


# ---------- modelos de entrada ----------
class NextIn(BaseModel):
    rotina: str
    seq: list[str] = []
    k: int = 5


class SpeakIn(BaseModel):
    seq: list[str]
    contexto: list[str] = []   # cards da frase anterior (memória da sessão)


@app.get("/api/config")
def config():
    return {"cards": DATA["cards"], "categories": DATA["categories"], "rotinas": ROTINAS,
            "sempre_visiveis": DATA["sempre_visiveis"]}


@app.post("/api/next")
def nxt(body: NextIn):
    t0 = time.perf_counter()
    ids, fonte = predict_next(body.rotina, [s for s in body.seq if s in CARDS], body.k)
    return {"sugestoes": ids, "fonte": fonte, "ms": round((time.perf_counter() - t0) * 1000, 2)}


@app.post("/api/speak")
def speak(body: SpeakIn):
    """Router: regra (0 ms de modelo) -> SLM -> fallback."""
    t0 = time.perf_counter()
    seq = ordenar(body.seq)   # corrige a ordem: "cabeça" + "dor" -> "dor" + "cabeça"
    frase = sentence_with_context(seq, body.contexto) or rule_sentence(seq)
    fonte = "regra"
    if frase is None:
        try:
            frase = compor(seq)          # compositor gramatical: qualquer nº de cards com sentido
        except Exception as e:
            print("compor falhou:", e)
            frase = None
        if frase: fonte = "compositor"
    if frase is None:
        fonte = "fallback"
        if SLM_URL:
            try:
                frase, fonte = slm_sentence(seq), "slm"
                motivo = verificar(seq, frase)           # GUARDA: o SLM omitiu ou inventou algo?
                if motivo:
                    print(f"SLM reprovado ({motivo}): {seq} -> {frase!r}")
                    frase = lista_sentence(seq)
                    fonte = f"lista (SLM reprovado: {motivo})" if frase else f"fallback (SLM reprovado: {motivo})"
            except Exception as e:
                print("SLM falhou, usando fallback:", e)
        if not frase:
            frase = fallback_sentence(seq)
    return {"frase": frase, "ordem": seq, "fonte": fonte, "ms": round((time.perf_counter() - t0) * 1000, 2)}


_yolo = {"ready": False, "model": None, "extra": None, "erro": None}


def _load_yolo():
    if not _yolo["ready"]:
        _yolo["ready"] = True
        try:
            from ultralytics import YOLO
            local = ROOT / "models" / "yolov8n.pt"
            _yolo["model"] = YOLO(os.environ.get("YOLO_WEIGHTS", str(local) if local.exists() else "yolov8n.pt"))   # COCO
            extra = ROOT / "models" / "falapicto_yolo.pt"     # opcional: ajustado com material escolar (lápis, apontador...)
            if extra.exists():
                _yolo["extra"] = YOLO(str(extra))
        except Exception as e:
            _yolo["erro"] = str(e)[:200]
            print("YOLO indisponível:", e)
    return _yolo["model"]


@app.get("/api/health")
def health():
    """Diagnóstico rápido para testar no celular: abra /api/health no navegador do aparelho."""
    return {"ok": True, "yolo": _yolo["model"] is not None, "yolo_extra": _yolo["extra"] is not None, "yolo_erro": _yolo["erro"],
            "lstm": bool(_lstm["model"]), "slm": bool(SLM_URL), "cards": len(CARDS)}


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


@app.post("/api/detect")
def detect(file: UploadFile = File(...)):   # def (não async): a inferência roda em thread e não trava o servidor
    _load_yolo()
    if _yolo["model"] is None:
        return {"disponivel": False, "objetos": [], "mensagem": "Reconhecimento de objetos não está ativo neste servidor."}
    from PIL import Image
    img = Image.open(io.BytesIO(file.file.read())).convert("RGB")
    W, H = img.size
    mapa = DATA["objetos_coco"]
    cand = []                                   # (card|None, conf, box_pixels, origem)
    res = _yolo["model"](img, verbose=False)[0]
    for b in res.boxes:
        nome = res.names[int(b.cls)]
        cand.append((mapa.get(nome), float(b.conf), [float(v) for v in b.xyxy[0]], "coco"))
    suprime = []                                # caixas de objetos que o YOLO pré-treinado não conhece (ex.: apontador)
    if _yolo["extra"] is not None:
        r2 = _yolo["extra"](img, verbose=False)[0]
        for b in r2.boxes:
            nome = r2.names[int(b.cls)]; conf = float(b.conf); box = [float(v) for v in b.xyxy[0]]
            if conf < 0.35: continue
            if nome in CARDS: cand.append((nome, conf, box, "extra"))
            else: suprime.append(box)           # classe conhecida mas sem card: só impede um falso 'copo' em cima dela
    achados = {}
    for card, conf, box, origem in cand:
        if not card or conf < 0.35: continue
        if origem == "coco" and any(_iou(box, s2) > 0.5 for s2 in suprime): continue
        if conf > achados.get(card, {"conf": 0})["conf"]:
            x1, y1, x2, y2 = box
            achados[card] = {"card": card, "conf": round(conf, 2),
                             "box": [round(x1 / W, 3), round(y1 / H, 3), round(x2 / W, 3), round(y2 / H, 3)]}
    objs = sorted(achados.values(), key=lambda o: -o["conf"])
    return {"disponivel": True, "objetos": objs}


app.mount("/static", StaticFiles(directory=ROOT / "web"), name="static")
(ROOT / "data" / "uploads").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=ROOT / "data" / "uploads"), name="uploads")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ROOT / "web" / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/admin")
def admin_page():
    return FileResponse(ROOT / "web" / "admin.html")


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")