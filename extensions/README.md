# Extensions

Local checkouts of add-on modules for development. Every subdirectory with a
`pyproject.toml` is installed in editable mode when the backend containers start
(`backend/scripts/start/install_extensions.sh`), and its entry point under
`open_wearables.extensions` is picked up by the core.

```bash
git clone <extension repo> extensions/<name>
docker compose up -d
```

With `ENVIRONMENT=local` the API reloads on its own when an extension's code changes; Celery
does not:

```bash
docker compose restart celery-worker celery-beat
```

To remove an extension, delete its directory and restart the backend containers
(`docker compose restart app celery-worker celery-beat`), which uninstalls it. A checkout
that fails to install is skipped with a warning instead of stopping the backend.

Everything in this directory except this README is git-ignored.
