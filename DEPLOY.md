# Deploy do FalaPicto (fora do PC)

A câmera do tablet só funciona em **https**. Duas formas:

## A) Hoje, em 10 min: túnel a partir do seu PC (sem conta de nuvem)
```bash
docker build -t falapicto .
docker run -d --name falapicto -p 8000:8000 -e ADMIN_PIN=1234abcd -v falapicto_dados:/app/data falapicto
# instale o cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
cloudflared tunnel --url http://localhost:8000
```
Ele imprime um link `https://xxxx.trycloudflare.com`. Abra no tablet (Chrome) →
menu ⋮ → **Adicionar à tela inicial**: abre em tela cheia como app. O PC precisa ficar ligado.
Sem Docker: `uvicorn api.main:app --port 8000` e o mesmo cloudflared.

## B) Servidor de verdade (serviço): qualquer VM Linux com Docker (≥ 2 GB RAM)
Azure/DigitalOcean/Oracle/Hetzner/etc. Aponte um domínio (ou subdomínio gratuito) para o IP da VM, libere as portas 80 e 443 e rode:
```bash
git clone <seu repo> && cd falapicto
export ADMIN_PIN=troque-isto DOMINIO=falapicto.seudominio.com
docker compose up -d                      # app + https automático
docker compose --profile slm up -d        # + SLM (llama.cpp) com models/falapicto-q4_k_m.gguf
# com SLM:  export SLM_URL=http://slm:8080  antes do up
```
Dados (cards, fotos cadastradas) ficam no volume `dados` — faça backup com
`docker run --rm -v falapicto_dados:/d -v $PWD:/b alpine tar czf /b/backup.tgz -C /d .`

## Privacidade (para o relatório)
- `/api/detect` processa a foto em memória e **não grava** a imagem.
- Sem login de criança, sem dados pessoais; só cards cadastrados pelo adulto.
- Painel `/admin` protegido por PIN (obrigatório em produção; o servidor recusa o PIN padrão).
- Em produção real: guardar consentimento do responsável (LGPD) e ter HTTPS (já incluso).
