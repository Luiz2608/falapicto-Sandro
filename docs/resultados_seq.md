| Modelo | Parâmetros | Top-1 | Top-3 | Acerto no card de retorno* | Latência/passo (ms) |
|---|---|---|---|---|---|
| N-gram (bigrama) | 0 | 52.4% | 84.8% | — | 0.00 |
| MLP (2 cards anteriores) | 19,885 | 52.2% ± 0.2 | 85.2% ± 0.1 | — | 0.03 |
| RNN | 10,861 | 52.8% ± 0.1 | 84.9% ± 0.1 | — | 0.06 |
| LSTM | 29,677 | 52.8% ± 0.2 | 85.2% ± 0.1 | — | 0.14 |

*card final de "eu quero X … mais X" (n=0 no teste). Só há retorno nos dados v2.
