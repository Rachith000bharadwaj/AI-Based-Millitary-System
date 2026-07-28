# AegisAI — Intelligence, Threat Prediction & Decision Support Platform

> Turning surveillance data into actionable intelligence.

A full-stack analyst workspace combining computer-vision object detection
(Ultralytics YOLOv8), machine-learning threat scoring (XGBoost), GIS
visualisation (React Leaflet), analytics (Recharts), PDF reporting (ReportLab)
and an optional generative assistant (Llama 3 via Groq), behind JWT
authentication with a full audit trail.

> [!IMPORTANT]
> **This is a demonstration system, not an operational one.**
> - Threat scores come from a model trained on **synthetic** telemetry. Real
>   military telemetry is classified and was not used.
> - Object detection uses **stock COCO-trained `yolov8n` weights**. COCO contains
>   no tank, UAV or military helicopter class. Military labels are produced by a
>   documented proxy mapping in [`api/services/taxonomy.py`](api/services/taxonomy.py).
> - Nothing here is accredited for operational use.

---

## Quick start

### Prerequisites
- **Node.js** 18.18+
- **Python** 3.10+
- **MongoDB**: Supports both **Local MongoDB** (`mongodb://127.0.0.1:27017`) and **Cloud MongoDB Atlas**. *(Optional — the API degrades gracefully in Mock Mode if MongoDB is offline)*

### 1. Configure Environment (`.env`)
```bash
cp .env.example .env
# Generate a signing key and paste it into JWT_SECRET_KEY:
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

#### 🗄️ Database Setup Options (`MONGO_URI` in `.env`):
* **Option A — Local MongoDB (Default for offline testing)**:
  ```env
  MONGO_URI=mongodb://127.0.0.1:27017/
  ```
* **Option B — Cloud MongoDB Atlas (Default for cloud deployment)**:
  ```env
  MONGO_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority
  ```
  > ⚠️ **Evaluator / Deployment Note**: When deploying on a new machine or submitting for evaluation, ensure your MongoDB Atlas IP Access List includes `0.0.0.0/0` (Allow Access from Anywhere) under **Security -> Network Access**, or switch `MONGO_URI` to a local MongoDB instance.

### 2. Install
```bash
npm install
pip install -r api/requirements.txt
```

### 3. Train the threat model
The trained artefacts are not committed; generate them once:
```bash
pip install -r api/requirements-dev.txt
python api/train_threat_model.py
```

### 4. Run (Single Command)
Run both the Next.js Frontend (`http://localhost:3000`) and the Python Flask Backend (`http://127.0.0.1:5332`) simultaneously in ONE terminal window:
```bash
npm run dev
```

*(Next.js automatically proxies `/api/*` requests to the Flask backend on port 5332).*

### 5. Create an account
Open <http://localhost:3000/security>, register an analyst, and sign in. Every
module requires authentication.

> To view the audit trail you need a `commander` or `admin` role. Self-service
> registration is restricted to `analyst`; promote a user directly in MongoDB:
> ```js
> db.users.updateOne({ username: "yourname" }, { $set: { role: "admin" } })
> ```

---

## Testing

```bash
pip install -r api/requirements-dev.txt
python -m pytest              # 105 backend tests, no MongoDB required
npx tsc --noEmit              # frontend type check
npx eslint .                  # frontend lint
npm run build                 # production build
```

The suite uses `mongomock`, so persistence paths are exercised without a running
database.

---

## Modules

| Route | Module | What it does |
| --- | --- | --- |
| `/dashboard` | Tactical Dashboard | Live KPIs, recent scores and 24h outlook, all from the API |
| `/detection` | Vision Engine | Upload imagery, run YOLO, view bounding-box overlay |
| `/predictive` | Predictive Intel | Score telemetry across six validated features |
| `/history` | Threat Intelligence | Full detection and assessment history |
| `/maps` | GIS Tactical Map | Threat, patrol and sensor markers with severity radii |
| `/data` | Data Hub | Aggregated analytics and PDF situation report export |
| `/assistant` | AI Assistant | Query recorded telemetry, draft reports |
| `/security` | Security Center | Login, registration, role-gated audit trail |
| `/settings` | Settings | Subsystem health, session info, known limitations |

Full endpoint reference: [`docs/api_documentation.md`](docs/api_documentation.md).

---

## Project structure

```
BSERC/
├── .env.example              # Configuration template (copy to .env)
├── next.config.mjs           # Next.js config incl. Flask proxy rewrites
├── pytest.ini                # Test configuration
│
├── app/                      # Next.js App Router pages
│   ├── layout.tsx            # Root layout, fonts, auth provider
│   ├── page.tsx              # Landing page
│   ├── globals.css           # Design tokens and shared styles
│   └── {assistant,dashboard,data,detection,history,maps,predictive,security,settings}/
│
├── components/               # Shared React components
│   ├── AppShell.tsx          # Responsive chrome (sidebar + navbar)
│   ├── Navbar.tsx
│   ├── Sidebar.tsx
│   └── ui.tsx                # Loading / error / empty / severity primitives
│
├── lib/                      # Frontend infrastructure
│   ├── api.ts                # Typed HTTP client, token handling
│   ├── auth-context.tsx      # Session state
│   ├── types.ts              # Shared API types
│   └── use-async-data.ts     # Cancellable data-fetching hook
│
├── api/                      # Flask backend
│   ├── app.py                # Application factory and entry point
│   ├── config.py             # Single source of configuration
│   ├── train_threat_model.py # Model training script
│   ├── database/             # MongoDB access layer
│   ├── middleware/           # Auth, authorisation, validation
│   ├── routes/               # Blueprints: threats, predict, assistant, auth, data
│   ├── services/             # Vision, ML, LLM, report, taxonomy
│   ├── tests/                # pytest suite
│   └── utils/                # Serialization, pagination
│
└── docs/                     # Architecture and API documentation
```

---

## Security

- **Passwords** — bcrypt with per-password salt and a configurable cost factor.
  Inputs over bcrypt's 72-byte limit are rejected with a 400, not a 500.
- **Tokens** — HS256 JWTs with a pinned algorithm (no `alg: none` confusion),
  required claims and short expiry. Held in `sessionStorage`, so they die with
  the tab.
- **Authorisation** — every data endpoint requires a token; the audit trail
  additionally requires `commander` or `admin`.
- **Uploads** — extension allowlist plus magic-number sniffing, a size cap, and
  randomised on-disk names. Frames are deleted after inference.
- **CORS** — scoped to configured origins, never `*`.
- **Errors** — internal exceptions are logged server-side; clients receive a
  generic message. Stack traces and driver errors are never returned.
- **Production guard** — the app refuses to boot in `FLASK_ENV=production`
  without a ≥32-byte `JWT_SECRET_KEY`, with debug on, or with wildcard CORS.

Secrets belong in `.env`, which is gitignored. Only `.env.example` is committed.

---

## Deployment notes

Do not use the Flask development server in production:

```bash
FLASK_ENV=production waitress-serve --port=5332 --call api.app:create_app
```

Set `JWT_SECRET_KEY`, `MONGO_URI` and `CORS_ORIGINS` in the environment. Build
the frontend with `npm run build && npm start`.

## Licence

See [LICENSE](LICENSE).
