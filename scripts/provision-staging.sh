#!/usr/bin/env bash
# Create the `directory` database on existing Cloud SQL instance db-dice.
# Do not create a separate instance. Do not run Django migrations against
# the `postgres` database (Sqitch / core.* live there).
set -euo pipefail

PROJECT="${PROJECT:-core-db-475718}"
INSTANCE="${INSTANCE:-db-dice}"
DB_NAME="${DB_NAME:-directory}"
CONNECTOR="${CONNECTOR:-projects/${PROJECT}/locations/us-central1/connectors/serverless-sql-connector}"

echo "Using project ${PROJECT}, instance ${INSTANCE}, database ${DB_NAME}"
gcloud config set project "${PROJECT}"

if ! gcloud sql instances describe "${INSTANCE}" --project "${PROJECT}" >/dev/null 2>&1; then
  echo "Instance ${INSTANCE} not found. Refusing to create a new instance." >&2
  exit 1
fi

if ! gcloud sql databases describe "${DB_NAME}" --instance="${INSTANCE}" --project="${PROJECT}" >/dev/null 2>&1; then
  gcloud sql databases create "${DB_NAME}" --instance="${INSTANCE}" --project="${PROJECT}"
else
  echo "Database ${DB_NAME} already exists on ${INSTANCE}."
fi

ensure_secret() {
  local name="$1"
  if gcloud secrets describe "${name}" --project="${PROJECT}" >/dev/null 2>&1; then
    echo "Secret ${name} exists."
  else
    echo "Creating placeholder secret ${name} (replace the value before serving traffic)."
    python - <<'PY' | gcloud secrets create "${name}" --project="${PROJECT}" --data-file=-
import secrets
print(secrets.token_urlsafe(48), end="")
PY
  fi
}

ensure_secret DIRECTORY_DJANGO_SECRET_KEY
ensure_secret DIRECTORY_SYNC_API_SECRET
ensure_secret DIRECTORY_DATABASE_URL

echo
echo "Next:"
echo "  1. Set DIRECTORY_DATABASE_URL to a unix-socket URL for ${INSTANCE}/${DB_NAME}"
echo "     (dbname=directory, host=/cloudsql/${PROJECT}:us-central1:${INSTANCE})."
echo "  2. SOURCE_DATABASE_URL for ETL points at ${INSTANCE}/postgres (core.*)."
echo "  3. Confirm SYNC_API_SECRET vs WP trigger secret are different values."
echo "  4. gcloud builds submit --config cloudbuild.yaml"
echo "Connector: ${CONNECTOR}"
