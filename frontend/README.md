# Open Wearables - Developer Portal

The admin dashboard for an Open Wearables deployment: users and their data,
syncs, webhooks, data coverage, and instance settings. Built with SvelteKit 2
(Svelte 5), Tailwind CSS v4 and Bun, rendered on the server.

The browser never talks to the API directly. It keeps the API tokens in an
`HttpOnly` cookie that page scripts cannot read, and the SvelteKit server calls
the backend on its behalf. The portal itself is stateless.

## Requirements

- [Bun](https://bun.sh) 1.4+
- A running Open Wearables backend

## Configuration

Copy the example and adjust it:

```sh
cp .env.example .env
```

| Variable       | Required | Purpose                                                                                                     |
| -------------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `VITE_API_URL` | yes      | Public URL of the API, as a browser or phone reaches it. Also used by the server when `API_URL` is not set. |
| `API_URL`      | no       | A shorter route from the portal's server to the API, e.g. `http://app:8000` inside Docker.                  |

Both are read at runtime, so one image works against any backend without a
rebuild.

## Development

```sh
bun install
bun run dev            # http://localhost:3000
```

With Docker, `docker compose watch` from the repository root runs the portal
together with the backend, with hot reload.

## Checks

```sh
bun run check          # svelte-check (types)
bun run lint           # eslint
bun run format         # prettier --write
bun run test:unit      # vitest: unit tests and component tests in Chromium
bun run test:e2e       # playwright against a production build and a mock API
```

`make frontend_verify` from the repository root runs everything CI runs.

## Production

```sh
bun run build
bun ./build/index.js   # listens on PORT (default 3000)
```

The published image is `themomentum/open-wearables-frontend`. See the
[Docker deployment guide](https://openwearables.io/docs/deployment/docker).

Conventions for contributors and coding agents are in [AGENTS.md](AGENTS.md).
