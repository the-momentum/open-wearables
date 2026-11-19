from __future__ import annotations

import re

import pulumi
import pulumi_gcp as gcp


def _slug(value: str, max_length: int = 30) -> str:
    slug = re.sub(r"[^a-z0-9-]", "-", value.lower()).strip("-")
    return (slug or "open-wearables")[:max_length].strip("-")


config = pulumi.Config()

project = config.get("project") or gcp.config.project
if not project:
    raise pulumi.ResourceError("Set gcp:project or open-wearables-cloudrun:project.", resource=None)

location = config.get("location") or gcp.config.region or "europe-west1"
service_name = config.get("serviceName") or "open-wearables"
init_job_name = config.get("initJobName") or f"{service_name}-init"
service_account_id = _slug(config.get("serviceAccountId") or f"{service_name}-run")

image = config.require("image")
db_host = config.require("dbHost")
db_name = config.get("dbName") or "open-wearables"
db_user = config.get("dbUser") or "open-wearables"
db_port = str(config.get_int("dbPort") or 5432)
db_password = config.require_secret("dbPassword")
secret_key = config.require_secret("secretKey")
admin_email = config.get("adminEmail") or "admin@admin.com"
admin_password = config.require_secret("adminPassword")

memory = config.get("memory") or "1Gi"
cpu = config.get("cpu") or "1"
timeout_seconds = config.get_int("timeoutSeconds") or 600
max_instances = config.get_int("maxInstances") or 4
min_instances = config.get_int("minInstances") or 0
concurrency = config.get_int("concurrency") or 1
allow_unauthenticated = config.get_bool("allowUnauthenticated")
if allow_unauthenticated is None:
    allow_unauthenticated = True

vpc_connector = config.get("vpcConnector")
vpc_egress = config.get("vpcEgress") or "PRIVATE_RANGES_ONLY"
enable_apis = config.get_bool("enableApis")
if enable_apis is None:
    enable_apis = True


enabled_services = []
if enable_apis:
    for api in ("run.googleapis.com", "secretmanager.googleapis.com"):
        enabled_services.append(
            gcp.projects.Service(
                _slug(api, max_length=50),
                project=project,
                service=api,
                disable_on_destroy=False,
            )
        )


service_account = gcp.serviceaccount.Account(
    "service-account",
    account_id=service_account_id,
    display_name=f"{service_name} Cloud Run",
    project=project,
    opts=pulumi.ResourceOptions(depends_on=enabled_services),
)


def make_secret(name: str, value: pulumi.Input[str]) -> gcp.secretmanager.Secret:
    secret = gcp.secretmanager.Secret(
        name,
        project=project,
        secret_id=f"{service_name}-{name}",
        replication={"auto": {}},
        opts=pulumi.ResourceOptions(depends_on=enabled_services),
    )
    gcp.secretmanager.SecretVersion(
        f"{name}-version",
        secret=secret.id,
        secret_data=value,
    )
    gcp.secretmanager.SecretIamMember(
        f"{name}-access",
        project=project,
        secret_id=secret.secret_id,
        role="roles/secretmanager.secretAccessor",
        member=service_account.member,
    )
    return secret


db_password_secret = make_secret("db-password", db_password)
secret_key_secret = make_secret("secret-key", secret_key)
admin_password_secret = make_secret("admin-password", admin_password)


def env(name: str, value: str) -> dict[str, str]:
    return {"name": name, "value": value}


def secret_env(name: str, secret: gcp.secretmanager.Secret) -> dict[str, object]:
    return {
        "name": name,
        "value_source": {
            "secret_key_ref": {
                "secret": secret.secret_id,
                "version": "latest",
            }
        },
    }


base_envs = [
    env("ENVIRONMENT", "production"),
    env("API_PORT", "8080"),
    env("TASK_EXECUTION_MODE", "inline"),
    env("SYNC_STATUS_ENABLED", "false"),
    env("OUTGOING_WEBHOOKS_ENABLED", "false"),
    env("RAW_PAYLOAD_STORAGE", "disabled"),
    env("DB_HOST", db_host),
    env("DB_PORT", db_port),
    env("DB_NAME", db_name),
    env("DB_USER", db_user),
    secret_env("DB_PASSWORD", db_password_secret),
    secret_env("SECRET_KEY", secret_key_secret),
    env("ADMIN_EMAIL", admin_email),
    secret_env("ADMIN_PASSWORD", admin_password_secret),
]

api_base_url = config.get("apiBaseUrl")
if api_base_url:
    base_envs.append(env("API_BASE_URL", api_base_url))

frontend_url = config.get("frontendUrl")
if frontend_url:
    base_envs.append(env("FRONTEND_URL", frontend_url))

cors_origins = config.get("corsOrigins")
if cors_origins:
    base_envs.append(env("CORS_ORIGINS", cors_origins))

template: dict[str, object] = {
    "service_account": service_account.email,
    "timeout": f"{timeout_seconds}s",
    "max_instance_request_concurrency": concurrency,
    "scaling": {
        "min_instance_count": min_instances,
        "max_instance_count": max_instances,
    },
    "containers": [
        {
            "image": image,
            "command": ["bash"],
            "args": ["scripts/start/app_cloudrun.sh"],
            "ports": [{"container_port": 8080}],
            "resources": {"limits": {"memory": memory, "cpu": cpu}},
            "envs": base_envs,
        }
    ],
}

if vpc_connector:
    template["vpc_access"] = {"connector": vpc_connector, "egress": vpc_egress}

service = gcp.cloudrunv2.Service(
    "service",
    project=project,
    name=service_name,
    location=location,
    deletion_protection=False,
    template=template,
    traffics=[{"type": "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST", "percent": 100}],
    opts=pulumi.ResourceOptions(
        depends_on=[
            service_account,
            db_password_secret,
            secret_key_secret,
            admin_password_secret,
        ]
    ),
)

if allow_unauthenticated:
    gcp.cloudrunv2.ServiceIamMember(
        "public-invoker",
        project=project,
        location=location,
        name=service.name,
        role="roles/run.invoker",
        member="allUsers",
    )

job_template: dict[str, object] = {
    "template": {
        "service_account": service_account.email,
        "max_retries": 1,
        "timeout": "1800s",
        "containers": [
            {
                "image": image,
                "command": ["bash"],
                "args": ["scripts/start/init_cloudrun.sh"],
                "resources": {"limits": {"memory": memory, "cpu": cpu}},
                "envs": base_envs,
            }
        ],
    }
}

if vpc_connector:
    job_template["template"]["vpc_access"] = {  # type: ignore[index]
        "connector": vpc_connector,
        "egress": vpc_egress,
    }

init_job = gcp.cloudrunv2.Job(
    "init-job",
    project=project,
    name=init_job_name,
    location=location,
    deletion_protection=False,
    template=job_template,
    opts=pulumi.ResourceOptions(
        depends_on=[
            service_account,
            db_password_secret,
            secret_key_secret,
            admin_password_secret,
        ]
    ),
)

pulumi.export("service_name", service.name)
pulumi.export("service_url", service.uri)
pulumi.export("init_job_name", init_job.name)
pulumi.export(
    "run_init_job",
    pulumi.Output.concat("gcloud run jobs execute ", init_job.name, " --region ", location, " --wait"),
)
