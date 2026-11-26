# Deploy e Contingência Offline — Aponta e Fala

A câmera do tablet (`getUserMedia`) exige **HTTPS** ou **`localhost`**. Abaixo estão os 3 modos de operação (do mais seguro para locais sem internet até o deploy em nuvem).

---

## A) Contingência 100% sem internet (Recomendado para demonstração em locais com Wi-Fi instável)

### Opção A1 — Cabo USB em tablet Android (câmera + IA 100% offline, zero configuração de certificado)
1. Ative a **Depuração USB** no tablet e conecte ao notebook.
2. Inicie o servidor local no notebook:
   ```powershell
   .\rodar_offline.ps1
   ```
3. Redirecione a porta `8000` para o tablet:
   - Via ADB: `adb reverse tcp:8000 tcp:8000`
   - Ou pelo Chrome do PC: abra `chrome://inspect/#devices` → *Port forwarding* → `8000` → `localhost:8000`.
4. No Chrome do tablet, abra **`http://localhost:8000`**.
   - Por ser `localhost`, o navegador libera a câmera, o Service Worker e a síntese de voz **sem internet e sem túnel**.

### Opção A2 — Rede local / Hotspot do celular (sem internet)
1. Conecte o notebook e o tablet ao mesmo Wi-Fi local ou Hotspot do celular.
2. Rode `.\rodar_offline.ps1` (mostra o IP local do notebook, ex.: `http://192.168.43.10:8000`).
3. Para liberar também a **câmera via HTTPS local** com Docker + Caddy (certificado autoassinado interno):
   - Substitua o volume do Caddyfile no `docker-compose.yml` por `./Caddyfile.local:/etc/caddy/Caddyfile:ro` e acesse `https://<IP-DO-NOTEBOOK>` aceitando o aviso de certificado local no tablet.

### O que acontece se a conexão cair no meio do uso?
- O **Service Worker (`/sw.js`)** mantém a interface, os cards e os ícones em cache.
- O **motor offline (`web/offline-core.js`)** monta as frases localmente em PT-BR e a **Web Speech API** fala normalmente no tablet.
- Um selo discreto (`Modo offline · prancha e voz ativas`) aparece no topo e desaparece automaticamente assim que a conexão com o servidor retornar.

---

## B) Túnel temporário com internet (`cloudflared`, sem conta de nuvem)
```bash
docker build -t aponta-e-fala .
docker run -d --name aponta-e-fala -p 8000:8000 -e ADMIN_PIN=1234abcd -v aponta_dados:/app/data aponta-e-fala
cloudflared tunnel --url http://localhost:8000
```
Abra o link `https://xxxx.trycloudflare.com` no tablet (Chrome → menu ⋮ → **Adicionar à tela inicial**). O link muda a cada reinício — por isso, para a feira/workshop, mantenha a **Opção A** pronta como contingência.

---

## C) Servidor dedicado (VM Linux com Docker ≥ 2 GB RAM)
Aponte um domínio para o IP da VM, libere as portas 80 e 443 e execute:
```bash
git clone https://github.com/Luiz2608/falapicto-Sandro.git && cd falapicto-Sandro
export ADMIN_PIN=troque-isto DOMINIO=apontaefala.seudominio.com
docker compose up -d                      # API + HTTPS automático (Let's Encrypt)
export SLM_URL=http://slm:8080/v1/chat/completions
docker compose --profile slm up -d        # + SLM (llama.cpp) com models/Qwen3-0.6B-curto.Q4_K_M.gguf
```

## Privacidade (LGPD)
- `/api/detect` processa os quadros de vídeo em memória e **não grava** imagens em disco.
- Sem login de criança e sem coleta de dados pessoais.
- Painel `/admin` protegido por PIN (em produção o servidor recusa o PIN padrão `1234`).
