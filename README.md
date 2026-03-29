# Brand Unsafe

**AI-powered brand compliance auditing for post-production video.**

Brand Unsafe scans video content for brand integration violations — catching shots where a sponsored brand appears alongside alcohol, a competitor, illegal activity, or any other prohibited context defined in a brand's contract. It runs as a web app, integrates directly with Frame.io, and produces timestamped compliance reports ready for delivery to brand managers.

Built for the TwelveLabs hackathon using the Marengo 2.7 and Pegasus 1.2 foundation models.

---

## The Problem

Brand integration deals are complex. A sports drink can't appear near alcohol. A luxury EV brand can't be seen in a street-racing context. An athletic apparel sponsor can't share the frame with a competitor's logo. Compliance teams currently scrub footage manually — frame by frame, clip by clip — before delivery. It's slow, expensive, and error-prone at scale.

Brand Unsafe automates the first pass.

---

## How It Works: Two-Pass Analysis

The core analysis uses two TwelveLabs models in sequence, which dramatically improves accuracy over a single-model approach.

### Pass 1 — Marengo 2.7: Brand Detection (Search)

Marengo's visual-semantic search engine scans the entire video to find every clip where the brand appears. Rather than using one long prose description (which degrades embedding search quality), Brand Unsafe generates short, focused queries:

- `"Nike"` — catches text on screen
- `"Nike logo"` — catches the graphic
- `"Nike product"` — catches apparel and packaging
- `"curved checkmark on athletic shoe"` — first sentence of the logo description for visual shape recall

Results from all queries are merged and deduplicated by timestamp. This gives high recall — every candidate clip reaches Pass 2.

### Pass 2 — Pegasus 1.2: Context Classification (Analyze)

For each brand appearance found in Pass 1, Pegasus analyzes the clip in full context against the brand's guidelines:

- Is the brand actually present (ruling out Marengo false positives)?
- Does the scene violate any prohibited context from the contract?
- If a violation, how severe is it (critical / moderate / minor)?

Pegasus returns structured JSON with a natural-language explanation specific enough for a brand manager to act on without watching the clip. The final confidence score blends Marengo's search score (40%) with Pegasus's classification confidence (60%).

Low-confidence detections are automatically flagged for human review rather than auto-classified.

```
┌─────────────────────────────────────────────────────────────────┐
│                          Video Input                            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Pass 1: Marengo    │  "Find every clip where
                    │  Visual Search      │   the brand appears"
                    └──────────┬──────────┘
                               │ candidate clips
                    ┌──────────▼──────────┐
                    │  Pass 2: Pegasus    │  "Is this a violation?
                    │  Context Analysis   │   How severe? Explain."
                    └──────────┬──────────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
        Compliant           Violation         Needs Review
                         (timestamped)       (human queue)
```

---

## Frame.io Integration

Brand Unsafe connects to Frame.io v4 via Adobe IMS OAuth. Once connected:

1. **Custom Action** — a "Submit for Compliance Review" button appears directly in Frame.io's right-click menu on any video asset.
2. **Webhook** — clicking the action triggers a webhook to the Brand Unsafe backend, which downloads the asset, runs the two-pass analysis, and posts the results back as a timestamped comment on the asset in Frame.io.
3. **Decision sync** — after a human reviewer approves or rejects the job in Brand Unsafe, the decision is posted back to Frame.io as a comment on the asset.

This means brand compliance review happens inside the editor's existing workflow — no context switching required.

---

## Features

- **Brand guidelines library** — JSON-based guidelines for each brand (logo description, prohibited contexts, required contexts, severity overrides). Pre-loaded with Nike, Adidas, Red Bull, Coca-Cola, Puma, PureFlow, NovaDrive, and StrideWear.
- **Compliance report** — timestamped list of every brand appearance with status (compliant / violation / needs_review), Pegasus's explanation, and severity rating.
- **Brand timeline** — visual timeline overlay on the video scrubber showing exactly when and where each appearance occurs.
- **Human review workflow** — reviewers can approve, reject, or escalate any completed audit. Decisions sync back to Frame.io.
- **Downloadable reports** — JSON export of the full compliance report for archival or delivery.
- **Persistent job history** — SQLite-backed job store; audit history survives server restarts.
- **Bring your own TwelveLabs key** — stored in the browser, never persisted on the server.

---

## Architecture

```
Browser (React + Vite)
    │
    └── FastAPI backend (Python)
            ├── POST /jobs              Upload video + guidelines → start audit
            ├── GET  /jobs/{id}         Poll job status + report
            ├── POST /jobs/{id}/review  Submit approval decision
            ├── GET  /oauth/login       Adobe IMS OAuth redirect
            ├── GET  /oauth/callback    Token exchange + persist
            ├── GET  /frameio/status    Verify Frame.io connection
            └── POST /frameio/webhook   Receive Frame.io custom action events

brand_compliance/
    ├── analyzer.py     Two-pass analysis (Marengo search → Pegasus classify)
    ├── indexer.py      TwelveLabs index creation + video upload
    ├── models.py       Violation, Appearance, Guidelines, ComplianceReport
    └── client.py       Singleton TwelveLabs client

guidelines/             JSON brand guidelines files
```

---

## Quick Start

### Requirements

- Python 3.11+
- Node.js 18+
- A [TwelveLabs API key](https://platform.twelvelabs.io)
- (Optional) Frame.io account + Adobe Developer OAuth app for the Frame.io integration

### Run locally

```bash
git clone https://github.com/your-org/brand-unsafe
cd brand-unsafe

pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

cp .env.example .env
# Edit .env — set TWELVELABS_API_KEY at minimum

uvicorn api.main:app --reload --port 8000
```

Open `http://localhost:8000`, enter your TwelveLabs API key, and upload a video with a brand guidelines file.

### Frame.io setup (optional)

1. Create a **Web App** OAuth credential at [developer.adobe.com/console](https://developer.adobe.com/console) for your Frame.io account.
2. Add to `.env`:
   ```
   FRAMEIO_CLIENT_ID     = your_client_id
   FRAMEIO_CLIENT_SECRET = your_client_secret
   FRAMEIO_REDIRECT_URI  = https://your-domain/oauth/callback
   ```
3. Go to **Integrations** in the app → click **Connect Frame.io**.
4. After connecting, register a Custom Action and Webhook from the Integrations page.

### Deploy to Railway

Set these environment variables in Railway's Variables tab:

| Variable | Description |
|---|---|
| `TWELVELABS_API_KEY` | Your TwelveLabs API key |
| `FRAMEIO_CLIENT_ID` | Adobe OAuth client ID |
| `FRAMEIO_CLIENT_SECRET` | Adobe OAuth client secret (copy from developer.adobe.com — regenerates after certain actions) |
| `FRAMEIO_REDIRECT_URI` | `https://<your-railway-domain>/oauth/callback` |
| `FRONTEND_URL` | `https://<your-railway-domain>` |

---

## Brand Guidelines Format

```json
{
  "brand": "Nike",
  "logo_description": "Nike Swoosh: a curved checkmark — wide on the right, tapering to a point on the left — printed in solid black or white on athletic shoes, jerseys, and apparel. The Swoosh appears on the shoe tongue, heel, and upper, and on the left chest of garments.",
  "contracted_screen_time_seconds": 45,
  "required_contexts": [
    "athletic performance or sports scenes",
    "training, exercise, or fitness activity"
  ],
  "prohibited_contexts": [
    "competitor brand logos or products (Adidas, Puma, Reebok, Under Armour)",
    "tobacco or alcohol products",
    "illegal activity or criminal behavior",
    "violence or weapons"
  ],
  "severity_overrides": {
    "competitor brand logos or products (Adidas, Puma, Reebok, Under Armour)": "critical",
    "tobacco or alcohol products": "critical"
  }
}
```

Guidelines can be created and edited from the **Policies** page in the app UI, or by dropping JSON files into the `guidelines/` directory.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Video AI | TwelveLabs Marengo 2.7 + Pegasus 1.2 |
| Backend | FastAPI, Python 3.11 |
| Frontend | React 18, TypeScript, Tailwind CSS, Vite |
| Storage | SQLite (jobs), local disk (video files) |
| Frame.io auth | Adobe IMS OAuth 2.0 |
| Deployment | Railway (Docker) |

---

## License

MIT
