#!/usr/bin/env bun
/**
 * Deploy orchestrator for Open Wearables on Fly.io.
 *
 *   bun run deploy                 # interactive picker
 *   bun run deploy api frontend    # deploy specific components
 *   bun run deploy all             # deploy everything in dependency order
 *   bun run deploy --list          # show components and exit
 *
 * Optional environment overrides:
 *   FLY_ORG, FLY_REGION, FLY_APP_PREFIX
 *   FLY_API_APP, FLY_FRONTEND_APP, FLY_FLOWER_APP, FLY_REDIS_APP, FLY_SVIX_APP
 *   FLY_API_URL, FLY_FRONTEND_URL, FLY_CORS_ORIGINS, FLY_SVIX_SERVER_URL
 */
import { $ } from "bun";

function env(name: string, fallback = ""): string {
  const value = process.env[name]?.trim();
  return value ? value : fallback;
}

const APP_PREFIX = env("FLY_APP_PREFIX", "open-wearables");
const ORG = env("FLY_ORG");
const REGION = env("FLY_REGION", "iad");

const API_APP = env("FLY_API_APP", `${APP_PREFIX}-api`);
const FRONTEND_APP = env("FLY_FRONTEND_APP", `${APP_PREFIX}-frontend`);
const FLOWER_APP = env("FLY_FLOWER_APP", `${APP_PREFIX}-flower`);
const REDIS_APP = env("FLY_REDIS_APP", `${APP_PREFIX}-redis`);
const SVIX_APP = env("FLY_SVIX_APP", `${APP_PREFIX}-svix`);

const API_URL = env(
  "FLY_API_URL",
  env("API_BASE_URL", `https://${API_APP}.fly.dev`),
);
const FRONTEND_URL = env("FLY_FRONTEND_URL", `https://${FRONTEND_APP}.fly.dev`);
const CORS_ORIGINS = env("FLY_CORS_ORIGINS", FRONTEND_URL);
const REDIS_HOST = env("FLY_REDIS_HOST", `${REDIS_APP}.internal`);
const SVIX_SERVER_URL = env(
  "FLY_SVIX_SERVER_URL",
  `http://${SVIX_APP}.flycast:8071`,
);

type Component = {
  key: string;
  app: string;
  summary: string;
  /** Lower runs first (broker before consumers, api image before flower). */
  order: number;
  deploy: () => Promise<void>;
};

async function ensureApp(app: string): Promise<void> {
  const existing = await $`fly apps list`.text().catch(() => "");
  if (existing.split(/\r?\n/).some((line) => line.split(/\s+/)[0] === app)) {
    return;
  }

  console.log(`  - creating app ${app}${ORG ? ` in org ${ORG}` : ""}`);
  if (ORG) {
    await $`fly apps create ${app} --org ${ORG}`;
  } else {
    await $`fly apps create ${app}`;
  }
}

/** Current backend image ref, so Flower runs the exact same code as the API. */
async function backendImageRef(): Promise<string> {
  const out = await $`fly image show -a ${API_APP}`.text();
  const tag = out.match(/deployment-[A-Z0-9]+/)?.[0];
  if (!tag) {
    throw new Error(`Could not resolve ${API_APP} image. Deploy 'api' first.`);
  }
  return `registry.fly.io/${API_APP}:${tag}`;
}

function randomHex(bytes = 16): string {
  const a = new Uint8Array(bytes);
  crypto.getRandomValues(a);
  return [...a].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const COMPONENTS: Component[] = [
  {
    key: "redis",
    app: REDIS_APP,
    summary: "internal Redis broker / OAuth-state store (private 6PN only)",
    order: 0,
    async deploy() {
      await ensureApp(this.app);
      await $`fly deploy --config deploy/fly/redis.toml --app ${this.app} --primary-region ${REGION} --image redis:8-alpine --ha=false`;
    },
  },
  {
    key: "api",
    app: API_APP,
    summary: `FastAPI + Celery worker/beat -> ${API_URL}`,
    order: 1,
    async deploy() {
      await ensureApp(this.app);
      await $`fly deploy --config fly.toml --app ${this.app} --primary-region ${REGION} --env API_BASE_URL=${API_URL} --env REDIS_HOST=${REDIS_HOST} --env SVIX_SERVER_URL=${SVIX_SERVER_URL} --env CORS_ORIGINS=${CORS_ORIGINS} --ha=false`.cwd(
        "backend",
      );
    },
  },
  {
    key: "flower",
    app: FLOWER_APP,
    summary: "Celery dashboard (public, basic auth) - reuses the API image",
    order: 2,
    async deploy() {
      await ensureApp(this.app);
      const secrets = await $`fly secrets list -a ${this.app}`
        .text()
        .catch(() => "");
      if (!secrets.includes("FLOWER_BASIC_AUTH")) {
        const pw = randomHex();
        console.log(`  - setting FLOWER_BASIC_AUTH = admin:${pw}  (save this)`);
        await $`fly secrets set -a ${this.app} FLOWER_BASIC_AUTH=${`admin:${pw}`}`;
      }
      const image = await backendImageRef();
      await $`fly deploy --config deploy/fly/flower.toml --app ${this.app} --primary-region ${REGION} --image ${image} --env REDIS_HOST=${REDIS_HOST} --ha=false`;
    },
  },
  {
    key: "frontend",
    app: FRONTEND_APP,
    summary: `Nitro web app -> ${API_URL}`,
    order: 3,
    async deploy() {
      await ensureApp(this.app);
      await $`fly deploy --config fly.toml --app ${this.app} --primary-region ${REGION} --env VITE_API_URL=${API_URL} --ha=false`.cwd(
        "frontend",
      );
    },
  },
  {
    key: "svix",
    app: SVIX_APP,
    summary: "Svix webhook server (internal). Needs secrets; see DEPLOY-FLY.md",
    order: 4,
    async deploy() {
      await ensureApp(this.app);
      const secrets = await $`fly secrets list -a ${this.app}`
        .text()
        .catch(() => "");
      for (const req of ["SVIX_JWT_SECRET", "SVIX_DB_DSN", "SVIX_REDIS_DSN"]) {
        if (!secrets.includes(req)) {
          throw new Error(
            `${this.app} is missing secret ${req}. Set the Svix secrets first (see DEPLOY-FLY.md), then re-run.`,
          );
        }
      }
      await $`fly deploy --config deploy/fly/svix.toml --app ${this.app} --primary-region ${REGION} --image svix/svix-server:v1 --ha=false`;
    },
  },
];

function resolve(tokens: string[]): Component[] {
  if (tokens.includes("all")) {
    return [...COMPONENTS].sort((a, b) => a.order - b.order);
  }

  const picked = new Map<string, Component>();
  for (const token of tokens) {
    const component =
      COMPONENTS.find((c) => c.key === token) ?? COMPONENTS[Number(token) - 1]; // allow 1-based menu numbers
    if (!component) {
      console.error(`Unknown component: "${token}"`);
      process.exit(1);
    }
    picked.set(component.key, component);
  }
  return [...picked.values()].sort((a, b) => a.order - b.order);
}

function printList(): void {
  console.log("\nConfiguration:");
  console.log(`  region:        ${REGION}`);
  console.log(`  org:           ${ORG || "(flyctl default)"}`);
  console.log(`  api URL:       ${API_URL}`);
  console.log(`  frontend URL:  ${FRONTEND_URL}`);
  console.log(`  Redis host:    ${REDIS_HOST}`);
  console.log(`  Svix URL:      ${SVIX_SERVER_URL}`);

  console.log("\nComponents:");
  COMPONENTS.forEach((c, i) =>
    console.log(
      `  ${i + 1}. ${c.key.padEnd(9)} ${c.app.padEnd(26)} ${c.summary}`,
    ),
  );
  console.log("  *. all       deploy everything in dependency order\n");
}

async function main(): Promise<void> {
  let tokens = process.argv.slice(2);

  if (tokens.includes("--list") || tokens.includes("-l")) {
    printList();
    return;
  }

  if (tokens.length === 0) {
    printList();
    const answer = prompt(
      "Deploy which? (names or numbers, comma/space separated, or 'all'):",
    );
    if (!answer?.trim()) {
      console.log("Nothing selected.");
      return;
    }
    tokens = answer.split(/[\s,]+/).filter(Boolean);
  }

  const selected = resolve(tokens);
  console.log(`\nWill deploy: ${selected.map((c) => c.key).join(", ")}\n`);

  const failed: string[] = [];
  for (const c of selected) {
    console.log(
      `\n-- deploying ${c.key} (${c.app}) ----------------------------`,
    );
    try {
      await c.deploy();
      console.log(`${c.key} deployed`);
    } catch (err) {
      console.error(
        `${c.key} failed: ${err instanceof Error ? err.message : err}`,
      );
      failed.push(c.key);
    }
  }

  console.log("\n--------------------------------");
  console.log(
    `Done. ${selected.length - failed.length}/${selected.length} succeeded.`,
  );
  if (failed.length) {
    console.log(`Failed: ${failed.join(", ")}`);
    process.exit(1);
  }
}

main();
