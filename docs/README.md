# Open Wearables Documentation

This directory houses the documentation site built with Mintlify.

## Development

Install the [Mintlify CLI](https://www.npmjs.com/package/mint) to preview your documentation changes locally. To install, use the following command:

```
npm i -g mint
```

Run the following command at the root of your documentation, where your `docs.json` is located:

```
mint dev --port 3333
```

(port `3000` is already being used by the frontend)

View your local preview at `http://localhost:3333` (or the port you specified).

## API Reference

The API Reference tab is built from `openapi.json` in this directory. The file is generated from the backend code and must not be edited by hand. Regenerate it from the repository root with:

```bash
cd backend && uv run python scripts/export_openapi.py
```

A pre-commit hook does this automatically when routes or schemas change, and CI fails if the committed file is stale.

## Publishing changes

Install our GitHub app from your [dashboard](https://dashboard.mintlify.com/settings/organization/github-app) to propagate changes from your repo to your deployment. Changes are deployed to production automatically after pushing to the default branch.

## Need help?

### Troubleshooting

- If your dev environment isn't running: Run `mint update` to ensure you have the most recent version of the CLI.
- If a page loads as a 404: Make sure you are running in a folder with a valid `docs.json`.

### Resources
- [Mintlify documentation](https://mintlify.com/docs)
