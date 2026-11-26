# Aponta e Fala — comunicação alternativa por pictogramas e câmera com SLM destilado

Ferramenta de **apoio à comunicação aumentativa e alternativa (CAA)** para crianças não verbais ou com dificuldade de fala (não substitui acompanhamento clínico/terapêutico).
A criança toca em cards de pictogramas ou aponta a câmera do tablet para um objeto; ao tocar em **Falar**, o sistema monta a frase em português natural e a reproduz em voz alta. Tudo roda **localmente** (em CPU, sem APIs pagas e sem coletar dados da criança) e continua funcionando mesmo em **locais com internet instável ou sem conexão**.

- **Disciplinas:** Redes Neurais Artificiais (RNA) e Tópicos em Engenharia de Software II (SLM) — FASOFT/UniRV (Prof. Sandro Silva Moreira)
- **Equipe:**
  - **Henrique Thomaz Landim Ruffato:** arquitetura e API (FastAPI), roteador de frases (regras, compositor, guarda), destilação e treino do SLM, ajuste do YOLO, LSTM, empacotamento em Docker e acesso pelo tablet.
  - **Luiz Eduardo Santos Silva:** correções críticas no fluxo de interface, fala e limpeza da prancha, refinamento das regras gramaticais de ajuda/ordenação, implementação da resiliência offline e tolerância a quedas de rede (Service Worker, motor local de frases, circuit breaker e contingência local), testes no tablet, gestão do repositório e consolidação da documentação de engenharia.

---

## Como rodar

### 1. Local (Python / desenvolvimento)
```bash
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics opencv-python-headless
uvicorn api.main:app --host 0.0.0.0 --port 8000
```
Abra `http://localhost:8000` no navegador.
> **Nota sobre o SLM (`.gguf`):** o modelo quantizado `Qwen3-0.6B-curto.Q4_K_M.gguf` (397 MB) excede o limite de 100 MB por arquivo do GitHub e, por isso, não é versionado no Git. Ele é gerado pelo notebook `src/03_slm_qlora_quantizacao.ipynb` e colocado em `models/`. Com o servidor `llama.cpp` rodando, defina `SLM_URL=http://localhost:8080/v1/chat/completions`. Sem o SLM, o roteador usa regras + compositor + fallback determinístico normalmente.

### 2. Docker (API + SLM + HTTPS)
```bash
docker build -t aponta-e-fala .
docker run -d --name aponta-e-fala -p 8000:8000 -e ADMIN_PIN=troque-aqui -v aponta_dados:/app/data aponta-e-fala
```
Com `docker compose` (incluindo servidor `llama.cpp` com `models/Qwen3-0.6B-curto.Q4_K_M.gguf`):
```bash
export ADMIN_PIN=troque-aqui SLM_URL=http://slm:8080/v1/chat/completions
docker compose --profile slm up -d
```

---

## Modo offline e locais com internet instável

O sistema foi projetado com **resiliência em camadas** para não travar nem ficar mudo caso o Wi-Fi oscile ou a internet caia durante o uso ou a demonstração:

1. **PWA + Service Worker (`/sw.js`) e cache em `localStorage`:** depois da primeira abertura, toda a prancha (HTML, ícones, `cards.json` e tabela N-grama) fica salva no tablet e abre mesmo sem internet.
2. **Motor determinístico offline no navegador (`web/offline-core.js`):** se `/api/speak` falhar ou exceder o timeout (4 s), o tablet ordena os cards, monta a frase em PT-BR localmente e fala via **Web Speech API (`speechSynthesis`)** — sem silêncio e sem erro.
3. **Interface otimista + sugestões offline:** cada toque desenha imediatamente (`0 ms`), nunca travando à espera da rede; se `/api/next` exceder 1,2 s, a sugestão de próximo card cai automaticamente para a tabela N-grama local.
4. **Câmera com timeout e backoff exponencial:** se o servidor cair durante o uso da câmera, a tela avisa que a prancha continua ativa offline e reconecta automaticamente quando a rede volta.
5. **Circuit breaker no SLM (`api/main.py`):** se o servidor `llama.cpp` demorar ou cair, a API ativa fallback imediato (< 1 ms) por 30 s e tenta novamente depois.
6. **Contingência 100% sem internet para demonstração (`rodar_offline.ps1`):**
   - **Windows:** execute `.\rodar_offline.ps1` para subir localmente na rede Wi-Fi/Hotspot ou via **cabo USB Android** (`adb reverse tcp:8000 tcp:8000` ou `chrome://inspect/#devices` → *Port forwarding* `8000 → localhost:8000`), abrindo `http://localhost:8000` no tablet com câmera, YOLO, LSTM, SLM e voz 100% sem internet.
   - Veja mais detalhes (incluindo HTTPS local com `Caddyfile.local` e túnel `cloudflared`) em [DEPLOY.md](DEPLOY.md).

---

## Cadastro de cards (`/admin`)
Abra `/admin` e entre com o PIN (`ADMIN_PIN`, padrão `1234` em dev; obrigatório trocar em produção):
- Cria, edita, ordena e remove cards, categorias, ícones (emoji ou upload de pictograma) e rotinas (grade fixa 3×3, máx. 9 por rotina) sem reiniciar o servidor.
- Persistência atômica em `data/cards.json` (com cópia `.bak`).

---

## Arquitetura resumida
```
Tablet (PWA / Web Speech API / Service Worker / offline-core.js)
   │
   ▼  (HTTP/HTTPS local, cabo USB ou túnel)
API FastAPI (container Docker, CPU)
   ├─ GET  /api/config, /api/ngram, /sw.js, /api/health
   ├─ POST /api/next    → LSTM (PyTorch, 0,15 ms) ── fallback → N-grama
   ├─ POST /api/detect  → YOLOv8n (COCO 12 classes) + YOLOv8n ajustado (7 classes escolares, supressão IoU>0,5)
   └─ POST /api/speak   → ordenar → contexto → regras → compositor → SLM Qwen3-0.6B (llama.cpp + circuit breaker) → guarda → fallback
```

---

## Principais resultados validados
- **SLM (`Qwen3-0.6B`, QLoRA `r=16`, 6 épocas, 234 exemplos curados do Gemini):** acerto exato de **70,8%** (24 exemplos de teste) em `f16`, `q8_0` e `q4_k_m`; produção em **`q4_k_m` (397 MB)** com latência média de **894 ms** (redução de 2,54 s no modo com pensamento para 0,89 s sem pensamento) e **87,5%** de fidelidade aos cards ([docs/resultados_slm_curto.md](docs/resultados_slm_curto.md)).
- **Roteador + Compositor + Guarda:** validado em ~34 mil combinações sem omitir ou inventar cards; respostas por regra/compositor em **< 2 ms**.
- **Visão (`YOLOv8n` transfer learning, 7 classes escolares):** **mAP50 = 0,749** e **mAP50-95 = 0,528** na validação; mesclado em tempo real com 12 classes do COCO.
- **Próximo card (`LSTM` vs. `RNN`, `MLP` e `N-grama`):** **Top-1 55,7%**, **Top-3 85,7%**, latência **0,15 ms/passo** e **100%** de acerto no card de retorno com dependência a distância (vs. 52,9% MLP e 34,8% N-grama) ([docs/resultados_seq_v2.md](docs/resultados_seq_v2.md)).

---

## Status atual (Checklist)
- [x] Vocabulário funcional (43 cards em 6 categorias, 7 rotinas + 4 sempre visíveis) e painel `/admin` com PIN
- [x] Correção de ordem dos cards, regras, compositor gramatical, memória de contexto e guarda anti-invenção
- [x] Treino e comparação N-grama / MLP / RNN / LSTM (`models/lstm.pt`, `docs/resultados_seq_v2.md`)
- [x] Ajuste fino do YOLOv8n para material escolar (`models/falapicto_yolo.pt`) + supressão de falsos positivos
- [x] Destilação (Gemini → 234 exemplos), QLoRA no Qwen3-0.6B, quantização GGUF e benchmark (`docs/resultados_slm_curto.md`)
- [x] Empacotamento Docker (API + SLM), voz apenas ao tocar em "Falar" e testes no tablet
- [x] Resiliência a quedas de internet (Service Worker, motor offline em JS, circuit breaker do SLM e script local/USB)
- [x] Documento de engenharia com Diagrama de Arquitetura ([docs/Aponta_e_Fala_Documentacao_Engenharia.pdf](docs/Aponta_e_Fala_Documentacao_Engenharia.pdf))
- [ ] Testes de borda no local do evento (iluminação e objetos fora das 7 classes)
- [ ] Substituição dos emojis por pictogramas definitivos (ex.: ARASAAC — validar licença)
- [ ] Roteiro final de demonstração (2–3 min) e troca do `ADMIN_PIN` antes da apresentação

## Limitações declaradas
- Os dados de treino do SLM (234 exemplos) e da LSTM são sintéticos; o sistema ainda não foi testado com crianças.
- `caneta` e `lápis` são as classes mais desafiadoras no YOLO ajustado, e `tesoura` teve apenas 4 amostras na validação.
