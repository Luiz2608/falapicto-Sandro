| Modelo | Parâmetros | Top-1 | Top-3 | Acerto no card de retorno* | Latência/passo (ms) |
|---|---|---|---|---|---|
| N-gram (bigrama) | 0 | 52.0% | 84.5% | 34.8% | 0.00 |
| MLP (2 cards anteriores) | 19,885 | 53.1% ± 0.1 | 84.9% ± 0.5 | 52.9% ± 0.6 | 0.03 |
| RNN | 10,861 | 55.5% ± 0.3 | 85.7% ± 0.0 | 100.0% ± 0.0 | 0.05 |
| LSTM | 29,677 | 55.7% ± 0.7 | 85.7% ± 0.3 | 100.0% ± 0.0 | 0.15 |

*card final de "eu quero X … mais X" (n=419 no teste). Só há retorno nos dados v2.
