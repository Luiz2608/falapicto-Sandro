| Modelo | Tamanho (MB) | Acerto exato | Exato (só combinações sem regra) | Fiel aos cards | Formato válido | Latência média (ms) | Latência p95 (ms) | Tokens/s |
|---|---|---|---|---|---|---|---|---|
| curto f16 | 1198 | 70.8% | 40.0% (n=5) | 83.3% | 100.0% | 2351 | 2771 | 8.5 |
| curto q8_0 | 639 | 70.8% | 40.0% (n=5) | 83.3% | 100.0% | 1446 | 1659 | 13.9 |
| curto q4_k_m | 397 | 70.8% | 40.0% (n=5) | 87.5% | 100.0% | 894 | 1100 | 22.5 |
| com pensamento q4_k_m | 397 | 54.2% | 40.0% (n=5) | 83.3% | 100.0% | 2544 | 2950 | 22.7 |
24 exemplos de teste · temperatura 0 · latência medida ponta a ponta na máquina atual.

**Erros de curto f16** (até 15):

- `Cards: Mamãe, Bravo` → esperado: Mamãe, estou bravo. | modelo: Mamãe, estou com bravo.
- `Cards: Eu quero, Garrafa, Lanche` → esperado: Eu quero a garrafa e o lanche. | modelo: Eu quero uma garrafa de lanche.
- `Cards: Ajuda, Amigo` → esperado: Amigo, preciso de ajuda. | modelo: Amigo, estou ajudando.
- `Cards: Banheiro` → esperado: Preciso ir ao banheiro. | modelo: Estou no banheiro.
- `Cards: Eu quero, Mochila, Banana, Por favor` → esperado: Eu quero a mochila e a banana, por favor. | modelo: Eu quero uma mochila e uma banana, por favor.
- `Cards: Não quero, Copo` → esperado: Não quero o copo. | modelo: Não quero um copo.
- `Cards: Não quero, Mochila, Atividade` → esperado: Eu não quero mochila nem atividade. | modelo: Não quero uma mochila e atividade.

**Erros de curto q8_0** (até 15):

- `Cards: Mamãe, Bravo` → esperado: Mamãe, estou bravo. | modelo: Mamãe, estou com bravo.
- `Cards: Eu quero, Garrafa, Lanche` → esperado: Eu quero a garrafa e o lanche. | modelo: Eu quero uma garrafa de lanche.
- `Cards: Ajuda, Amigo` → esperado: Amigo, preciso de ajuda. | modelo: Amigo, estou ajudando.
- `Cards: Banheiro` → esperado: Preciso ir ao banheiro. | modelo: Estou no banheiro.
- `Cards: Eu quero, Mochila, Banana, Por favor` → esperado: Eu quero a mochila e a banana, por favor. | modelo: Eu quero uma mochila e uma banana, por favor.
- `Cards: Não quero, Copo` → esperado: Não quero o copo. | modelo: Não quero um copo.
- `Cards: Não quero, Mochila, Atividade` → esperado: Eu não quero mochila nem atividade. | modelo: Não quero uma mochila e atividade.

**Erros de curto q4_k_m** (até 15):

- `Cards: Mamãe, Bravo` → esperado: Mamãe, estou bravo. | modelo: Mamãe, estou com o bravo.
- `Cards: Eu quero, Garrafa, Lanche` → esperado: Eu quero a garrafa e o lanche. | modelo: Eu quero uma garrafa de lanche.
- `Cards: Não quero, Lápis` → esperado: Não quero o lápis. | modelo: Não quero lápis.
- `Cards: Banheiro` → esperado: Preciso ir ao banheiro. | modelo: Estou no banheiro.
- `Cards: Eu quero, Mochila, Banana, Por favor` → esperado: Eu quero a mochila e a banana, por favor. | modelo: Eu quero uma mochila e uma banana, por favor.
- `Cards: Não quero, Copo` → esperado: Não quero o copo. | modelo: Não quero um copo.
- `Cards: Não quero, Mochila, Atividade` → esperado: Eu não quero mochila nem atividade. | modelo: Não quero uma mochila e fazer atividade.

**Erros de com pensamento q4_k_m** (até 15):

- `Cards: Terminei, Lanche` → esperado: Terminei o lanche. | modelo: Terminei meu lanche.
- `Cards: Medo` → esperado: Estou com medo. | modelo: Eu tenho medo.
- `Cards: Mamãe, Bravo` → esperado: Mamãe, estou bravo. | modelo: Mamãe, bravo!
- `Cards: Eu quero, Garrafa, Lanche` → esperado: Eu quero a garrafa e o lanche. | modelo: Eu quero uma garrafa de lanche.
- `Cards: Feliz, Mamãe` → esperado: Mamãe, estou feliz. | modelo: Estou felizmente sendo mamãe.
- `Cards: Ajuda, Amigo` → esperado: Amigo, preciso de ajuda. | modelo: Preciso de ajuda com o amido.
- `Cards: Eu quero, Amigo` → esperado: Eu quero o amigo. | modelo: Eu quero amigo.
- `Cards: Bravo, Amigo` → esperado: Amigo, estou bravo. | modelo: Bravo, estou amando você.
- `Cards: Banheiro` → esperado: Preciso ir ao banheiro. | modelo: Peço ao banheiro.
- `Cards: Eu quero, Mochila, Banana, Por favor` → esperado: Eu quero a mochila e a banana, por favor. | modelo: Eu quero uma mochila e uma banana, por favor.
- `Cards: Não quero, Mochila, Atividade` → esperado: Eu não quero mochila nem atividade. | modelo: Não quero a mochila e não vou a atividade.
