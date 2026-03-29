# Brand Compliance Auditor

Automatically audits videos uploaded to Frame.io against brand guidelines using TwelveLabs AI. When a video is uploaded, a webhook triggers a two-pass analysis (semantic search + Pegasus verification) and posts a compliance report as a comment directly on the asset in Frame.io.

## How it works

1. Video uploaded to Frame.io
2. Frame.io webhook fires → FastAPI receives it
3. Video downloaded and indexed in TwelveLabs
4. Two-pass brand compliance analysis runs (Marengo search → Pegasus verify)
5. Compliance report posted back as a comment on the Frame.io asset

## Prerequisites

- Python 3.12+
- Node.js 18+
- [TwelveLabs](https://twelvelabs.io) account and API key
- [Frame.io](https://app.frame.io) account
- Adobe Developer Console project with a Frame.io Web App OAuth credential
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) or ngrok for HTTPS tunneling

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in:
- `TWELVELABS_API_KEY` — from [twelvelabs.io](https://twelvelabs.io)
- `FRAMEIO_ACCOUNT_ID` — visible in Frame.io URLs or API responses
- `FRAMEIO_CLIENT_ID` / `FRAMEIO_CLIENT_SECRET` — from Adobe Developer Console (see below)

### 3. Create Frame.io OAuth credentials (Adobe Developer Console)

1. Go to [developer.adobe.com/console](https://developer.adobe.com/console)
2. Create a new project → Add API → Frame.io
3. Choose **Web App** credential type
4. Set redirect URI to `https://<your-tunnel-url>/oauth/callback`
5. Set redirect URI pattern to `https://.*\.trycloudflare\.com/oauth/callback` (or your tunnel domain)
6. Copy Client ID and Client Secret into `.env`

### 4. Start a HTTPS tunnel

```bash
cloudflared tunnel --url http://localhost:8000
```

Copy the `https://...trycloudflare.com` URL. Set it in `.env`:
```
FRAMEIO_REDIRECT_URI = https://<tunnel-url>/oauth/callback
```

### 5. Start the backend

```bash
cd /path/to/LaHackathon && uvicorn api.main:app --reload --port 8000
```

### 6. Authenticate with Frame.io

Open in your browser:
```
https://<tunnel-url>/oauth/login
```

Authorize with Adobe. The access and refresh tokens are written to `.env` automatically.

### 7. Register the Frame.io webhook

```bash
python scripts/setup_frameio_webhook.py https://<tunnel-url>
```

This registers the webhook with Frame.io and saves the signing secret to `.env`.

### 8. Start the frontend (optional)

```bash
cd frontend && npm run dev
```

## Usage

Upload any video to your Frame.io workspace. Within a minute or two, a brand compliance report will appear as a comment on the asset.

## Brand guidelines

Guidelines live in `guidelines/` as JSON files. Three examples are included:
- `pureflow_water.json`
- `novadrive_ev.json`
- `stridewear_apparel.json`

The backend uses `pureflow_water.json` by default. To add your own, follow the same schema.
