# ChatKit Starter

Minimal Vite + React UI paired with a FastAPI backend that forwards chat
requests to OpenAI through the ChatKit server library.

## Quick start

```bash
npm install
npm run dev
```

What happens:

- `npm run dev` starts the FastAPI backend on `127.0.0.1:8000` and the Vite
  frontend on `127.0.0.1:3000` with a proxy at `/chatkit`.

## Required environment

- `OPENAI_API_KEY` (backend)
- `OPENAI_VECTOR_STORE_ID` (backend, required after syncing the ARUN corpus)
- `ARUN_KB_ROOT` (optional, defaults to the local `ARUN data` folder)
- `ARUN_KB_MANIFEST_PATH` (optional, defaults to `backend/.arun_kb_manifest.json`)
- `DATABASE_URL` (backend persistence for chat threads and history)
- `CORS_ALLOWED_ORIGINS` (comma-separated allowlist for frontend origins)
- `VITE_CHATKIT_API_URL` (optional, defaults to `/chatkit`)
- `VITE_CHATKIT_API_DOMAIN_KEY` (optional, defaults to `domain_pk_localhost_dev`)
- `VITE_AUTH0_DOMAIN` (frontend/runtime, required for login gating)
- `VITE_AUTH0_CLIENT_ID` (frontend/runtime, required for login gating)
- `VITE_AUTH0_AUDIENCE` (frontend/runtime, required for API access tokens)

Set `OPENAI_API_KEY` in your shell or in `.env` at the repo root before
running the backend. Register a production domain key in the OpenAI dashboard
and set `VITE_CHATKIT_API_DOMAIN_KEY` when deploying.

For Auth0, configure the SPA application with these URLs:

- Allowed Callback URLs: `http://localhost:3000/`, `https://<your-frontend-domain>/`
- Allowed Logout URLs: `http://localhost:3000/`, `https://<your-frontend-domain>/`
- Allowed Web Origins: `http://localhost:3000`, `https://<your-frontend-domain>`
- API Identifier / Audience: match `VITE_AUTH0_AUDIENCE`

Run database migrations as part of your deploy/release process.

## ARUN knowledge-base sync

The backend is configured for a pre-indexed ARUN retrieval corpus:

- top-level `*.docx` files inside `ARUN data`
- `juicing_YT_raw_transcripts/*.txt`

The sync command uploads those files into OpenAI Files, creates or reuses a
vector store, and writes an incremental manifest locally.

```bash
cd chatkit/backend
./scripts/run.sh
```

In a separate shell, run:

```bash
cd chatkit/backend
.venv/bin/python -m app.sync_arun_kb
```

Or after the editable install is available:

```bash
cd chatkit/backend
sync-arun-kb
```

If the sync command creates a new vector store, it prints the resulting
`OPENAI_VECTOR_STORE_ID`. Add that value to your `.env` before starting
the backend for normal use.

## Customize

- Update UI and connection settings in `frontend/src/lib/config.ts`.
- Adjust layout in `frontend/src/components/ChatKitPanel.tsx`.
- Swap the in-memory store in `backend/app/server.py` for persistence.
- Extend `backend/app/sync_arun_kb.py` if you want to add deletion cleanup or
  support more source formats later.
