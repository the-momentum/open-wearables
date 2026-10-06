# Extensions

Local checkouts of add-on modules for development. Every subdirectory with a
`pyproject.toml` is installed in editable mode when the backend containers start
(`backend/scripts/start/install_extensions.sh`), and its entry point under
`open_wearables.extensions` is picked up by the core.

```bash
git clone <extension repo> extensions/<name>
docker compose up -d
```

Everything in this directory except this README is git-ignored. See
`docs/dev-guides/extensions.mdx` for how to write an extension.
