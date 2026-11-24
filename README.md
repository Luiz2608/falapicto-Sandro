# FalaPicto — comunicação alternativa com SLM local

Ferramenta de **apoio à comunicação** (não é dispositivo terapêutico) para crianças com dificuldade de fala.
A criança toca em cards (pictogramas) ou aponta a câmera para um objeto; o tablet fala a frase. Tudo roda **local**, sem internet, sem coletar dados da criança.

Projeto integrador: **Tópicos em Eng. de Software II (SLM)** + **Redes Neurais**.

## Como rodar
```bash
pip install -r requirements.txt
cd src && python gen_data.py && python slm_dataset.py semente && cd ..
uvicorn api.main:app --port 8000      # abrir http://localhost:8000 no tablet/navegador
```
Opcionais: `pip install torch` (ativa o LSTM) e `pip install ultralytics` (ativa o YOLO). Sem eles a API usa N-gram e avisa que a câmera não está ativa.
Com Docker: `docker build -t falapicto . && docker run -p 8000:8000 falapicto`.

## Testar a câmera no celular/tablet
A câmera do navegador só abre em **https** ou em `localhost`. Duas formas:
1. **Túnel https** (qualquer celular): `uvicorn api.main:app --port 8000` e, em outro terminal, `cloudflared tunnel --url http://localhost:8000`. Abra o endereço `https://….trycloudflare.com` no aparelho. Feche o túnel ao terminar e troque o `ADMIN_PIN`.
2. **Android por cabo USB** (sem expor nada): depurar USB ligado, Chrome do PC em `chrome://inspect/#devices` → *Port forwarding* 8000 → `localhost:8000`; no celular abra `http://localhost:8000`.
Diagnóstico: abra `/api/health` no aparelho (mostra se YOLO, LSTM e SLM estão ativos).

## Cadastro de cards (fonoaudiólogas e professoras)
Abra **http://localhost:8000/admin** e entre com o PIN (padrão `1234` — **troque**):
```powershell
$env:ADMIN_PIN="seu-pin-aqui"      # Windows PowerShell (Mac/Linux: export ADMIN_PIN=...)
uvicorn api.main:app --port 8000
```
Lá dá para criar, editar e apagar cards: legenda, tipo (define a cor), cor própria, ícone (emoji ou imagem/pictograma enviado), fala ao tocar, como entra na frase ("a bola", "pintar"), em quais rotinas aparece (máx. 9 por rotina) e a ordem dos cards. As mudanças valem na hora, sem reiniciar. O arquivo `data/cards.json` guarda tudo (com cópia `.bak` a cada salvamento) e as imagens ficam em `data/uploads/`.
Limitação: cards novos ainda não entram nas sugestões do LSTM (ele foi treinado com os cards originais). Para incluí-los: ajustar `GRAMATICA` em `src/gen_data.py`, rodar `gen_data.py --v2` e `train_seq.py --data seqs_v2.jsonl --tag _v2 --save`.

## Arquitetura
```
Tablet (web) ──► API local (FastAPI)
                  ├─ /api/detect  YOLO (COCO + ajuste) → card do objeto
                  ├─ /api/next    LSTM → destaca próximo card provável (posições FIXAS, só destaca)
                  └─ /api/speak   ROUTER: regra (~0,02 ms) → SLM quantizado (llama.cpp) → fallback
```

## Mapa disciplina → projeto
| Tópico | Onde |
|---|---|
| MLP / RNN / LSTM | `src/train_seq.py` (+ baseline N-gram) → `docs/resultados_seq.md` |
| CNN / YOLO | `/api/detect` (YOLO nano; classes COCO → cards) |
| Dataset PT-BR + curadoria | `src/slm_dataset.py` (semente por regras, prompt p/ Gemini, filtros) |
| Destilação + QLoRA | `src/03_slm_qlora_quantizacao.ipynb` (Qwen3-0.6B) |
| Quantização FP16/INT8/INT4 | mesmo notebook (GGUF f16 / q8_0 / q4_k_m) |
| Camada de roteamento | `api/main.py` → `/api/speak` |
| API local + container | `Dockerfile` |
| LGPD / privacidade | sem dados reais; tudo local; dados sintéticos |

## Scripts de medição (para o relatório)
```bash
cd src
python avaliar_yolo.py fotos                       # fotos/<id_do_card>/*.jpg -> docs/resultados_yolo.md
python benchmark_slm.py --modelo "q4_k_m|http://localhost:8083/v1/chat/completions|gguf_q4_k_m/modelo.gguf" ...   # docs/resultados_slm.md
```
O prompt do SLM é **único** (`core.prompt_messages`): treino, API e benchmark usam exatamente o mesmo formato.

## Estado atual (honesto)
- [x] Vocabulário provisório (43 cards, 7 rotinas) — **trocar após a entrevista**
- [x] Regras de frase, router, API, tela (testados)
- [x] Cards coloridos por tipo, ícones SVG (barriga/cabeça) e tela de cadastro com PIN (testada no navegador)
- [x] Dados sintéticos + N-gram
- [ ] Treino MLP/RNN/LSTM (ver `docs/resultados_seq.md` se já rodou)
- [ ] YOLO: instalar ultralytics e medir quais objetos o COCO já acerta
- [ ] SLM: gerar dados com Gemini, curar, treinar no Colab, quantizar, medir
- [ ] Pictogramas reais (ex.: ARASAAC — checar licença) no lugar dos emojis
- [ ] Entrevista com a especialista → ajustar cards, rotinas e frases
- [ ] Relatório e slides

## Limitações a declarar no relatório
- Os dados são sintéticos: as métricas medem o aprendizado da gramática definida por nós, **não** o uso real por crianças.
- Validação real = opinião da especialista sobre o protótipo (sem teste com criança).
