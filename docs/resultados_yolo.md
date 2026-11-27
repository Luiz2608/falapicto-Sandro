# Resultados de Validação — YOLOv8n Ajustado (Material Escolar)

Avaliação do modelo `models/falapicto_yolo.pt` treinado por *transfer learning* a partir de `yolov8n.pt` (COCO) no Google Colab (GPU T4, 60 épocas, `imgsz=640`, `batch=16`, `patience=15`, `seed=0`) com o notebook [`src/04_yolo_ajuste.ipynb`](../src/04_yolo_ajuste.ipynb) e esquema de classes definido em [`docs/yolo_data.yaml`](yolo_data.yaml).

## Resumo do dataset e métricas globais

- **Origem dos dados:** datasets abertos do Roboflow Universe (CC BY 4.0) mesclados via [`src/mesclar_datasets.py`](../src/mesclar_datasets.py).
- **Volume efetivo na execução do Colab:** **2.538 imagens** no treino e **149 imagens** na validação (pacote mesclado completo: 2.595 treino / 154 validação / 125 teste, após descarte automático de imagens sem rótulo válido pelo Ultralytics).
- **mAP50 geral (validação):** **0,749**
- **mAP50-95 geral (validação):** **0,528**
- **Limiar de confiança na API (`/api/detect`):** `0,35` (combinado em tempo real com 12 classes do `YOLOv8n` COCO e supressão de falsos positivos de `copo` por `IoU > 0,5`).

## Desempenho por classe (validação)

| Classe (id do card) | Rótulo na prancha | mAP50 (val) | Observação |
|---|---|:---:|---|
| `tesoura` | Tesoura | **0,99** | Apenas 4 amostras na validação (índice estatisticamente frágil) |
| `caderno` | Caderno | **0,79** | Boa separação visual |
| `regua` | Régua | **0,79** | Boa separação visual |
| `apontador` | Apontador | **0,77** | Suprime falsos `copo` do COCO quando sobreposto (`IoU > 0,5`) |
| `borracha` | Borracha | **0,74** | Desempenho estável |
| `lapis` | Lápis | **0,65** | Objeto fino; mais sensível a ângulo e iluminação |
| `caneta` | Caneta | **0,51** | Classe mais desafiadora (confusão visual com `lapis`) |
| **Geral (7 classes)** | — | **0,749** | **mAP50-95 = 0,528** (149 imagens de validação) |

## Reprodução
- Treino e validação no Colab: [`src/04_yolo_ajuste.ipynb`](../src/04_yolo_ajuste.ipynb).
- Avaliação por objeto no fluxo da API (com fotos próprias organizadas em `fotos/<id_do_card>/`):
  ```bash
  python src/avaliar_yolo.py fotos --pesos models/falapicto_yolo.pt --classes-sao-cards
  ```
