# AI Creator Studio

Customer-facing application for generating AI influencer images, talking-head videos, and short cinematic clips, designed for Google Cloud (`us-central1`) with on-demand Cloud Run GPU Jobs (`nvidia-l4`) and optional hosted premium providers (Seedance / Kling).

## Architecture

```
ai-creator-studio/
├── frontend/          # React + Vite + TypeScript + Tailwind CSS + TanStack Query
├── backend/           # FastAPI (Auth, Jobs, Signed URLs, Providers, Admin)
├── gpu-worker/        # ComfyUI + Python batch runner for Cloud Run GPU Jobs
└── infra/             # Cloud Build & gcloud deployment scripts
```

## Quick Start (Local Development)

### 1. Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Demo accounts (seeded automatically in `local` mode):
- **Customer**: `creator@example.com` / `creator123`
- **Admin**: `admin@example.com` / `admin123`

### 2. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to `http://localhost:8000`.

### 3. Docker Compose (Optional)

```bash
docker compose up --build
```

## GCP Deployment

See `infra/deploy.sh` and `infra/cloudbuild.yaml` for deploying to a GCP project in `us-central1`:
1. Enable Cloud Run, Artifact Registry, Cloud Build, Cloud Storage, Cloud Tasks, Secret Manager, IAM, and Firestore APIs.
2. Create private GCS bucket with uniform bucket-level access & public access prevention.
3. Create least-privilege service accounts (`ai-api`, `ai-gpu-job`, `ai-web`).
4. Build and deploy `gpu-worker` (Cloud Run GPU Job with `nvidia-l4`), `backend` (Cloud Run Service), and `frontend` (Cloud Run Service).
