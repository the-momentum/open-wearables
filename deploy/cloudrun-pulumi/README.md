# Open Wearables Cloud Run Pulumi

This deploys the backend as a single Cloud Run service using the Redis-free serverless profile:

- `TASK_EXECUTION_MODE=inline`
- `SYNC_STATUS_ENABLED=false`
- `OUTGOING_WEBHOOKS_ENABLED=false`
- no Celery worker, no Celery beat, no Redis, no Svix

The app still needs PostgreSQL reachable from Cloud Run over TCP. For Cloud SQL private IP, create a Serverless VPC Access connector and set `vpcConnector`.

## Files

- `__main__.py`: generic Pulumi program.
- `deploy-to-gcp.sh`: account-oriented wrapper that sets Pulumi config from environment variables and runs `pulumi up`.
- `Pulumi.account.yaml.example`: stack config template.
- `spec/cloudrun-service.yaml`: Cloud Run service spec only.
- `spec/cloudrun-init-job.yaml`: Cloud Run init job spec only.

## Generic Pulumi Usage

```bash
cd deploy/cloudrun-pulumi
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

pulumi stack init prod
pulumi config set gcp:project YOUR_PROJECT_ID
pulumi config set gcp:region europe-west1
pulumi config set location europe-west1
pulumi config set image europe-west1-docker.pkg.dev/YOUR_PROJECT_ID/REPO/open-wearables-backend:TAG
pulumi config set dbHost 10.0.0.3
pulumi config set dbName open-wearables
pulumi config set dbUser open-wearables
pulumi config set corsOrigins '["https://your-frontend.example.com"]'
pulumi config set frontendUrl https://your-frontend.example.com

pulumi config set --secret dbPassword '...'
pulumi config set --secret secretKey '...'
pulumi config set --secret adminPassword '...'

pulumi up
pulumi stack output run_init_job
```

Run the printed init-job command once per deploy to apply migrations and seed reference data.

## Deploy Wrapper

```bash
cd deploy/cloudrun-pulumi
export STACK=prod
export PROJECT_ID=your-gcp-project-id
export REGION=europe-west1
export IMAGE=europe-west1-docker.pkg.dev/your-gcp-project-id/open-wearables/open-wearables-backend:latest
export DB_HOST=10.0.0.3
export DB_NAME=open-wearables
export DB_USER=open-wearables
export DB_PASSWORD='...'
export SECRET_KEY='...'
export ADMIN_EMAIL=admin@admin.com
export ADMIN_PASSWORD='...'
export FRONTEND_URL=https://your-frontend.example.com
export API_BASE_URL=https://your-cloud-run-url-or-custom-domain
export CORS_ORIGINS='["https://your-frontend.example.com"]'
# export VPC_CONNECTOR=projects/your-gcp-project-id/locations/europe-west1/connectors/open-wearables

./deploy-to-gcp.sh
```

## Spec-Only Usage

Create these secrets first:

```bash
gcloud secrets create open-wearables-db-password --replication-policy=automatic
printf '%s' 'DATABASE_PASSWORD' | gcloud secrets versions add open-wearables-db-password --data-file=-

gcloud secrets create open-wearables-secret-key --replication-policy=automatic
printf '%s' 'SECRET_KEY' | gcloud secrets versions add open-wearables-secret-key --data-file=-

gcloud secrets create open-wearables-admin-password --replication-policy=automatic
printf '%s' 'ADMIN_PASSWORD' | gcloud secrets versions add open-wearables-admin-password --data-file=-
```

Then replace placeholders in `spec/*.yaml` and deploy:

```bash
gcloud run services replace spec/cloudrun-service.yaml --region europe-west1
gcloud run jobs replace spec/cloudrun-init-job.yaml --region europe-west1
gcloud run jobs execute open-wearables-init --region europe-west1 --wait
```
