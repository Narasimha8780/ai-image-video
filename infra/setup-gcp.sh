#!/usr/bin/env bash
set -euo pipefail

# One-time GCP Foundation Setup for AI Creator Studio (us-central1)
# Usage: PROJECT_ID=your-gcp-project-id ./infra/setup-gcp.sh

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID}"
REGION="${REGION:-us-central1}"
BUCKET="${BUCKET:-ai-models}"
AR_REPO="${AR_REPO:-narasimha8780}"
QUEUE_NAME="ai-studio-jobs"

gcloud config set project "$PROJECT_ID"

echo "==> 1. Enabling required GCP APIs..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  cloudtasks.googleapis.com \
  secretmanager.googleapis.com \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  firestore.googleapis.com

echo "==> 2. Creating private Cloud Storage bucket (with public access prevention)..."
gcloud storage buckets create "gs://${BUCKET}" \
  --location="$REGION" \
  --uniform-bucket-level-access || true

gcloud storage buckets update "gs://${BUCKET}" \
  --public-access-prevention

echo "==> 3. Creating Artifact Registry Docker repository..."
gcloud artifacts repositories create "$AR_REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --description="AI Creator Studio containers" || true

echo "==> 4. Creating Firestore Native database (if not exists)..."
gcloud firestore databases create --location="$REGION" --type=firestore-native || true

echo "==> 5. Creating Cloud Tasks queue..."
gcloud tasks queues create "$QUEUE_NAME" \
  --location="$REGION" \
  --max-dispatches-per-second=2 \
  --max-concurrent-dispatches=4 || true

echo "==> 6. Creating least-privilege service accounts..."
gcloud iam service-accounts create ai-api --display-name="AI Studio API" || true
gcloud iam service-accounts create ai-gpu-job --display-name="AI Studio GPU Job" || true
gcloud iam service-accounts create ai-web --display-name="AI Studio Dashboard Web" || true

API_SA="ai-api@${PROJECT_ID}.iam.gserviceaccount.com"
GPU_SA="ai-gpu-job@${PROJECT_ID}.iam.gserviceaccount.com"

# Storage access
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${GPU_SA}" --role="roles/storage.objectAdmin"
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${API_SA}" --role="roles/storage.objectAdmin"

# Firestore access
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${API_SA}" --role="roles/datastore.user"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${GPU_SA}" --role="roles/datastore.user"

# Cloud Run Jobs & Cloud Tasks dispatch permissions for API SA
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${API_SA}" --role="roles/run.developer"
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${API_SA}" --role="roles/cloudtasks.enqueuer"
gcloud iam service-accounts add-iam-policy-binding "$API_SA" \
  --member="serviceAccount:${API_SA}" --role="roles/iam.serviceAccountTokenCreator"

# Grant Cloud Build service accounts permission to deploy Cloud Run services & GPU jobs
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
for CB_SA in "${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com" "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CB_SA}" --role="roles/run.admin"
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${CB_SA}" --role="roles/iam.serviceAccountUser"
done

echo "==> Setup complete! Next, deploy everything with:"
echo "    gcloud builds submit --config infra/cloudbuild.yaml ."
