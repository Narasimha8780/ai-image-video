#!/usr/bin/env bash
set -euo pipefail

# AI Creator Studio - GCP Deployment Script (us-central1)
# Usage: PROJECT_ID=my-gcp-project ./infra/deploy.sh

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
BUCKET="${PROJECT_ID}-creator-assets"
AR_REPO="ai-studio"
TAG="${TAG:-1}"

gcloud config set project "$PROJECT_ID"

echo "==> Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  cloudtasks.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  firestore.googleapis.com

echo "==> Creating private Cloud Storage bucket & Artifact Registry..."
gcloud storage buckets create "gs://${BUCKET}" \
  --location="$REGION" \
  --uniform-bucket-level-access || true

gcloud storage buckets update "gs://${BUCKET}" \
  --public-access-prevention

gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="AI Creator Studio containers" || true

echo "==> Creating least-privilege service accounts..."
gcloud iam service-accounts create ai-api --display-name="AI Studio API" || true
gcloud iam service-accounts create ai-gpu-job --display-name="AI Studio GPU Job" || true
gcloud iam service-accounts create ai-web --display-name="AI Studio Web" || true

API_SA="ai-api@${PROJECT_ID}.iam.gserviceaccount.com"
GPU_SA="ai-gpu-job@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${GPU_SA}" \
  --role="roles/storage.objectAdmin"

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${API_SA}" \
  --role="roles/storage.objectAdmin"

echo "==> Building images via Cloud Build..."
gcloud builds submit --config infra/cloudbuild.yaml --substitutions="_REGION=${REGION},_AR_REPO=${AR_REPO},_TAG=${TAG}" .

GPU_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/gpu-worker:${TAG}"
API_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/backend:${TAG}"
WEB_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/web:${TAG}"

echo "==> Creating Cloud Run GPU Jobs (NVIDIA L4)..."
gcloud run jobs deploy ai-image-worker \
  --image="$GPU_IMAGE" \
  --region="$REGION" \
  --service-account="$GPU_SA" \
  --cpu=4 --memory=16Gi \
  --gpu=1 --gpu-type=nvidia-l4 \
  --no-gpu-zonal-redundancy \
  --tasks=1 --parallelism=1 \
  --max-retries=1 \
  --task-timeout=3600

gcloud run jobs deploy ai-video-worker \
  --image="$GPU_IMAGE" \
  --region="$REGION" \
  --service-account="$GPU_SA" \
  --cpu=4 --memory=16Gi \
  --gpu=1 --gpu-type=nvidia-l4 \
  --no-gpu-zonal-redundancy \
  --tasks=1 --parallelism=1 \
  --max-retries=1 \
  --task-timeout=3600

echo "==> Deploying Backend API & React Web services..."
gcloud run deploy ai-studio-api \
  --image="$API_IMAGE" \
  --region="$REGION" \
  --service-account="$API_SA" \
  --set-env-vars="APP_ENV=gcp,GCP_PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},GCS_BUCKET=${BUCKET},LOCAL_SIMULATE_GPU=false" \
  --port=8080

gcloud run deploy ai-studio-web \
  --image="$WEB_IMAGE" \
  --region="$REGION" \
  --allow-unauthenticated \
  --port=8080

echo "==> Deployment complete!"
