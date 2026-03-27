#!/bin/bash
# One-time job to create the first admin user in Cloud Run
# Usage: ./create-admin-job.sh admin@example.com 'YourSecurePassword' 'Admin Name'

set -e

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <admin-email> <admin-password> [admin-name]"
  exit 1
fi

ADMIN_EMAIL="$1"
ADMIN_PASSWORD="$2"
ADMIN_NAME="${3:-Admin}"

PROJECT_ID="${PROJECT_ID:-g-tele-educacion-dev-prj-d18a}"
REGION="${REGION:-us-east1}"
CLOUD_SQL_INSTANCE="${CLOUD_SQL_INSTANCE:-${PROJECT_ID}:${REGION}:supervisor-ia}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-educacion-svc-dev@${PROJECT_ID}.iam.gserviceaccount.com}"
BACKEND_IMAGE="${BACKEND_IMAGE:-${REGION}-docker.pkg.dev/${PROJECT_ID}/storymap/backend:latest}"

echo "Creating admin user job..."
gcloud run jobs create seed-admin-user \
  --image "$BACKEND_IMAGE" \
  --region "$REGION" \
  --service-account "$SERVICE_ACCOUNT" \
  --set-cloudsql-instances "$CLOUD_SQL_INSTANCE" \
  --set-secrets "DATABASE_URL=database-url-storymap:1" \
  --set-env-vars "SEED_ADMIN_EMAIL=${ADMIN_EMAIL},SEED_ADMIN_PASSWORD=${ADMIN_PASSWORD},SEED_ADMIN_NAME=${ADMIN_NAME}" \
  --execute-now \
  --wait \
  --command "python" \
  --args "scripts/seed_user.py" \
  --tasks 1 \
  --max-retries 0

echo ""
echo "✅ Admin user created!"
echo "   Email: ${ADMIN_EMAIL}"
echo "   Password: ${ADMIN_PASSWORD}"
echo ""
echo "Cleaning up job..."
gcloud run jobs delete seed-admin-user --region "$REGION" --quiet

echo "Done! You can now log in with these credentials."
