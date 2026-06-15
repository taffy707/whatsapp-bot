# Deploying the WhatsApp Bot 24/7 on an On-Prem Windows Server

This guide takes the bot from "runs on my laptop in a terminal" to "runs forever on a
Windows server, auto-starting on boot and auto-restarting on crash, reachable by Meta
over a permanent HTTPS URL."

Architecture:

```text
WhatsApp user
  → Meta WhatsApp Cloud API
  → https://vicki-nonideologic-sharri.ngrok-free.dev/webhook   (reserved ngrok domain)
  → ngrok agent (runs as a Windows service)
  → http://127.0.0.1:8000                                      (uvicorn, Windows service)
  → the agent → reply back to the user
```

Two background Windows services do the work:
- **WhatsAppBot** — the FastAPI/uvicorn webhook server.
- **ngrok** — the tunnel agent that exposes it publicly over HTTPS.

Neither needs an open inbound firewall port: ngrok makes an **outbound** connection, so it
works behind NAT / a normal router.

> **Why ngrok and not Cloudflare?** Your ngrok account already has a **reserved static
> domain** (`vicki-nonideologic-sharri.ngrok-free.dev`) and Meta's webhook is already
> registered against it. Reusing it means **zero new external setup and no domain to buy** —
> the webhook URL never changes. If you later outgrow ngrok's free tier (e.g. connection
> limits), see the "Alternative: Cloudflare Tunnel" appendix.

---

## Prerequisites

- A Windows server (or always-on Windows PC) with internet access that stays powered on.
- Admin rights on that server (needed to install services).
- The permanent WhatsApp **System User** access token (never expires) and the other
  WhatsApp credentials — same values as in your working `.env`.
- `ANTHROPIC_API_KEY` (and `TAVILY_API_KEY` only if you enable the web-search tool).
- Your **ngrok authtoken** — from <https://dashboard.ngrok.com/get-started/your-authtoken>
  (same account that owns the reserved domain).

> **One agent per domain:** a reserved ngrok domain can only be used by one running agent
> at a time. When the server goes live, **stop ngrok on the old machine** or the server's
> agent won't be able to claim the domain.

---

## Step 1 — Put the code on the server

Install **Python 3.11+** (<https://www.python.org/downloads/> — tick "Add to PATH") and
**Git** (<https://git-scm.com/download/win>). Then, in PowerShell:

```powershell
# Clone the repo
cd C:\
git clone https://github.com/taffy707/whatsapp-bot.git
cd C:\whatsapp-bot

# Create an isolated virtual environment
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Dependencies are declared in `pyproject.toml`. The simplest install on a fresh box:

```powershell
.\.venv\Scripts\python.exe -m pip install `
  "langgraph>=1.0.0" "langchain>=0.2.14" "langchain-anthropic>=0.1.23" `
  "langchain-openai>=0.1.22" "langchain-tavily>=0.1" "python-dotenv>=1.0.1" `
  "fastapi>=0.115.0" "uvicorn>=0.32.0" "httpx>=0.28.0" "pydantic>=2.10.0"
```

(Or install `uv` and run `uv pip install -r pyproject.toml`.)

### Create the `.env` file

The repo does **not** include `.env` (it holds secrets). Create `C:\whatsapp-bot\.env`
with your real values — these match your current working setup:

```dotenv
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=...            # only needed if the search tool is used

WHATSAPP_ACCESS_TOKEN=EAA...  # the PERMANENT System User token
WHATSAPP_PHONE_NUMBER_ID=1150304458171476   # +263 78 917 6485 (current production number)
WHATSAPP_BUSINESS_ACCOUNT_ID=1406920098101571
WHATSAPP_VERIFY_TOKEN=whatsapp_bot_verify_2024
WHATSAPP_APP_ID=1515089053607441
WHATSAPP_APP_SECRET=f38866994971af3c42481557f01ef4ce
```

> **Do not** copy the `SSL_CERT_FILE=...` line from the dev machine's `.env` — that path
> points at the old machine's venv. Omit it; if you later hit an SSL certificate error,
> set it to this server's path:
> `C:\whatsapp-bot\.venv\Lib\site-packages\certifi\cacert.pem`.

### Smoke-test it manually

```powershell
.\.venv\Scripts\python.exe -m uvicorn react_agent.whatsapp_webhook:app --host 127.0.0.1 --port 8000 --app-dir src
```

In another PowerShell window:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health   # -> @{status=healthy}
```

Press `Ctrl+C` to stop once it works. We'll make it permanent in Step 3.

---

## Step 2 — Set up ngrok on the server

1. Download ngrok for Windows from <https://ngrok.com/download> (or `winget install ngrok`),
   and put `ngrok.exe` somewhere stable, e.g. `C:\ngrok\ngrok.exe`.
2. Add your authtoken (same account that owns the reserved domain):

   ```powershell
   C:\ngrok\ngrok.exe config add-authtoken <YOUR-AUTHTOKEN>
   ```

3. **Stop ngrok on the old machine first** (so the domain is free), then test the tunnel
   on the server:

   ```powershell
   C:\ngrok\ngrok.exe http --url=vicki-nonideologic-sharri.ngrok-free.dev 8000
   ```

   With the bot running (Step 1 smoke-test), confirm from any machine:

   ```powershell
   Invoke-WebRequest "https://vicki-nonideologic-sharri.ngrok-free.dev/webhook?hub.mode=subscribe&hub.verify_token=whatsapp_bot_verify_2024&hub.challenge=OK"
   # Body should be exactly: OK
   ```

   Press `Ctrl+C` to stop; we make it a service next.

---

## Step 3 — Install both as auto-starting Windows services

### 3a. The bot as a service (via NSSM)

Download **NSSM** from <https://nssm.cc/download>, unzip, and use `win64\nssm.exe`.
In an **Administrator** PowerShell:

```powershell
C:\nssm\nssm.exe install WhatsAppBot
```

In the NSSM dialog:

- **Application → Path:** `C:\whatsapp-bot\.venv\Scripts\python.exe`
- **Application → Startup directory:** `C:\whatsapp-bot`
- **Application → Arguments:**
  `-m uvicorn react_agent.whatsapp_webhook:app --host 127.0.0.1 --port 8000 --app-dir src`
- **Details → Startup type:** `Automatic`
- (Optional) **I/O tab:** set Output/Error to e.g. `C:\whatsapp-bot\logs\bot.log` to capture logs.
- Click **Install service**, then:

```powershell
C:\nssm\nssm.exe start WhatsAppBot
```

### 3b. ngrok as a service

ngrok has built-in Windows service support. It reads the tunnel from a config file, so
first write one. Create `C:\ngrok\ngrok.yml`:

```yaml
version: "3"
agent:
  authtoken: <YOUR-AUTHTOKEN>
tunnels:
  whatsapp:
    proto: http
    addr: 8000
    url: vicki-nonideologic-sharri.ngrok-free.dev
```

Then install and start the service (Administrator PowerShell):

```powershell
C:\ngrok\ngrok.exe service install --config C:\ngrok\ngrok.yml
C:\ngrok\ngrok.exe service start
```

Both services now auto-start on boot and auto-restart on crash.

```powershell
# Useful commands
Get-Service WhatsAppBot, ngrok
C:\nssm\nssm.exe restart WhatsAppBot   # after a `git pull` or .env change
```

---

## Step 4 — Confirm Meta is happy (no changes needed)

Because the webhook URL is unchanged, there's nothing to reconfigure in Meta. Just verify
end-to-end:

1. Public reachability:

   ```powershell
   Invoke-WebRequest "https://vicki-nonideologic-sharri.ngrok-free.dev/webhook?hub.mode=subscribe&hub.verify_token=whatsapp_bot_verify_2024&hub.challenge=OK"
   # Body should be exactly: OK
   ```

2. Message the production number **+263 78 917 6485** from any phone — you should get a reply.

If you ever *do* need to re-point Meta (e.g. you switch domains): Meta app dashboard →
**WhatsApp → Configuration → Webhook → Edit** → set Callback URL + verify token
(`whatsapp_bot_verify_2024`) → subscribe to the **messages** field.

Done — the bot now runs 24/7, survives reboots, and keeps its permanent URL.

---

## Updating the bot later

```powershell
cd C:\whatsapp-bot
git pull
C:\nssm\nssm.exe restart WhatsAppBot
```

The ngrok domain and Meta webhook config never need to change.

---

## Troubleshooting

- **`failed to start tunnel: domain already in use`** — the reserved domain is still claimed
  by ngrok on another machine. Stop ngrok there (`Get-Process ngrok | Stop-Process`).
- **Meta verification fails / no messages arrive** — the bot or ngrok service is down. Check
  `Get-Service WhatsAppBot, ngrok` and the ngrok dashboard (<https://dashboard.ngrok.com>)
  for an active agent session.
- **Messages arrive but no reply is sent** — check the bot log for a WhatsApp API error.
  `190` = bad/expired access token (shouldn't happen with the permanent System User token);
  `131005` / `131030` = recipient restricted (only if the business were unverified — yours
  is verified).
- **`SSL: CERTIFICATE_VERIFY_FAILED`** — set `SSL_CERT_FILE` in `.env` to
  `C:\whatsapp-bot\.venv\Lib\site-packages\certifi\cacert.pem` and restart the service.
- **Conversation history resets after a reboot** — expected: the bot uses in-memory
  storage. To persist across restarts, switch to a SQLite/Postgres checkpointer
  (see `CLAUDE.md` → Conversation Memory).

---

## Alternative: Cloudflare Tunnel (if you outgrow ngrok free)

ngrok's free tier has connection/bandwidth limits suitable for low-volume support traffic.
For higher volume or to avoid ngrok entirely, use a Cloudflare Tunnel instead:

1. Buy a cheap domain (~$10/yr) and add it to a free Cloudflare account (change nameservers).
2. **Zero Trust dashboard → Networks → Tunnels → Create a tunnel** (Cloudflared) → install
   the connector on Windows with the provided token (it auto-registers as a service).
3. Add a **Public Hostname**: `whatsapp.<yourdomain>` → `http://localhost:8000`.
4. Re-point Meta's webhook to `https://whatsapp.<yourdomain>/webhook`.

Everything else (the bot service, `.env`) stays identical.
