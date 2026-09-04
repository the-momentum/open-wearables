# Svelte Frontend — Development Guide

Ground-up rewrite of the React dashboard in SvelteKit. Lives on the
`feat/svelte-frontend` branch and runs alongside the existing frontend until it
reaches parity; only then does `frontend/` get deleted.

**Status:** early. Container, design tokens, responsive shell, and
cookie-backed authentication with a sign-in screen. **No real pages yet** —
every destination under `(app)` is a placeholder. Read "Current state" before
assuming anything exists.

## Non-negotiable: latest SvelteKit, Svelte 5 runes

This is the single easiest thing to get wrong here, because most Svelte material
in circulation — blog posts, Stack Overflow answers, model training data —
describes **Svelte 4**, and it looks superficially correct.

**Always use the newest SvelteKit and Svelte 5.** Verify before assuming:

```bash
bun pm ls | grep -E 'svelte@|@sveltejs'      # what is installed
bun pm view svelte version                    # what is current
```

Verified current as of 2026-09-02 — all four at latest:

| Package                        | Installed |
| ------------------------------ | --------- |
| `svelte`                       | 5.57.0    |
| `@sveltejs/kit`                | 2.70.3    |
| `@sveltejs/adapter-node`       | 5.5.7     |
| `@sveltejs/vite-plugin-svelte` | 7.3.0     |

Runes mode is **forced on** in [vite.config.ts](vite.config.ts) for every file
outside `node_modules`, so the Svelte 4 component API is not merely discouraged
— it does not compile.

### Svelte 4 → 5 translation

If you catch yourself writing anything in the left column, stop.

| Svelte 4 (do not write)                | Svelte 5 runes                                            |
| -------------------------------------- | --------------------------------------------------------- |
| `export let foo`                       | `let { foo } = $props()`                                  |
| `let count = 0` (reactive by position) | `let count = $state(0)`                                   |
| `$: doubled = count * 2`               | `const doubled = $derived(count * 2)`                     |
| `$: { sideEffect() }`                  | `$effect(() => { sideEffect() })`                         |
| `on:click={handler}`                   | `onclick={handler}`                                       |
| `createEventDispatcher()`              | callback props: `let { onsave } = $props()`               |
| `<slot />`                             | `{@render children()}` with `let { children } = $props()` |
| `<slot name="header" />`               | snippet prop: `{@render header?.()}`                      |
| `writable()` + `$store`                | `$state` inside a `.svelte.ts` module                     |

Two mechanical traps:

- Runes only work in `.svelte` files and in modules named **`.svelte.ts`**. A
  plain `.ts` file cannot use `$state`; the rune is a compiler feature, not an
  import.
- `svelte/store` still exists and still works. That is a compatibility path, not
  a reason to reach for it. Prefer runes for new state.

### Documentation for agent sessions

`svelte.dev` publishes machine-readable docs — prefer these over recalled
knowledge, which skews Svelte 4:

- <https://svelte.dev/llms.txt> — index of the available sets
- <https://svelte.dev/llms-medium.txt> — abridged, legacy notes stripped
- <https://svelte.dev/docs/kit/llms.txt> — SvelteKit only
- <https://svelte.dev/docs/svelte/llms.txt> — Svelte only

## Relationship to `frontend/` (React)

`frontend/` is the live product and stays on `main`. Do not change it from this
branch.

This is **not a 1:1 port**. The React app is ~29k LOC across 175 files and
carries dead weight: unused SSR infrastructure, endpoint constants for routes
that were never built, three 800+ line components. Reproducing it faithfully
would reproduce that.

What to reuse and what to rethink:

| Layer                              | Approach                                                                                                          |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `src/lib/api/*`, `src/lib/utils/*` | Plain TypeScript, no React. Port selectively — copy what a slice needs, leave the rest.                           |
| Type definitions (`api/types.ts`)  | Copy the types a slice touches. Don't bulk-import all 881 lines.                                                  |
| Endpoint constants                 | Copy per slice. Several in the React version are marked "may not exist in backend yet" — do not carry those over. |
| Components                         | Rewrite. Do not transliterate JSX.                                                                                |
| Data fetching hooks                | Rewrite. See "Open decisions".                                                                                    |

The backend contract is unchanged, so `frontend/src/lib/api/` is the reference
for endpoint shapes and response types. Read it; don't copy it wholesale.

## Working agreements

These came from the project owner and override general habit.

1. **Just-in-time dependencies.** Do not install a package before the code that
   needs it exists. No "we'll want this later" installs. When you do add one,
   say what it buys and what the alternative was.
2. **Small increments.** One element at a time. Land it, show it, then move on.
   Do not batch a shell, an auth layer and three pages into one change.
3. **Tests alongside the code**, not in a cleanup pass afterwards. The React app
   has three test files, all on utils, and that is the single biggest risk in
   retiring it — do not repeat it here.
4. **Mobile-first.** The React dashboard is effectively unusable on a phone.
   Every layout starts at the small breakpoint and grows, never the reverse.
5. **Explain new concepts** rather than introducing them silently.

## Tech stack

Scaffolded with `sv create` (official Svelte CLI), not hand-written config.

| Concern                   | Choice                                        |
| ------------------------- | --------------------------------------------- |
| Framework                 | SvelteKit 2 / Svelte 5 (runes mode forced on) |
| Build                     | Vite 8                                        |
| Language                  | TypeScript 6, `strict`                        |
| Styling                   | Tailwind CSS v4 (no plugins)                  |
| Adapter                   | `@sveltejs/adapter-node`                      |
| Package manager / runtime | Bun 1.4                                       |
| Unit + component tests    | Vitest 4                                      |
| E2E                       | Playwright                                    |
| Lint / format             | ESLint 10 + Prettier                          |

### Config lives in `vite.config.ts`

There is **no `svelte.config.js`**. This scaffold puts SvelteKit options —
including `adapter` and `compilerOptions` — inside the `sveltekit()` plugin call
in [vite.config.ts](vite.config.ts). Most SvelteKit documentation and older
answers assume a separate file; they are describing an older layout.

Runes are forced on for all non-`node_modules` files, so `$state`/`$props`/
`$derived` are always available and the legacy `export let` API is not.

## Commands

```bash
bun run dev          # dev server on :3001
bun run build        # production build into build/
bun run preview      # serve the production build
bun run check        # svelte-check — run this before calling anything done
bun run lint         # prettier --check + eslint
bun run format       # prettier --write
bun run test:unit    # vitest (unit + component)
bun run test:e2e     # playwright
bun run test         # both
```

## Component granularity

**Components are atomic.** Split one as soon as any logic starts to grow — do
not wait for a line count. When a category directory fills up, split it into
subdirectories too. The target is a deep tree of small components, which is the
opposite of what `frontend/` became (`-seed-data-tab.tsx` is 1335 lines,
`connection-card.tsx` 830).

**This limit does not apply to test files** — see below.

## Testing

Three tiers, distinguished **by filename**. Getting the suffix wrong sends a
test to the wrong runner.

| Pattern             | Runner                                            | Use for                                               |
| ------------------- | ------------------------------------------------- | ----------------------------------------------------- |
| `*.spec.ts`         | Vitest, node environment                          | Pure logic: formatters, parsers, API request building |
| `*.browser.spec.ts` | Vitest, real Chromium via `vitest-browser-svelte` | Component rendering and interaction                   |
| `*.e2e.ts`          | Playwright against a production build on :4173    | Full flows: sign-in, navigation, a page loading data  |

`*.browser.spec.ts` is a deliberate rename from the scaffold's
`*.svelte.spec.ts`. The patterns are wired in [vite.config.ts](vite.config.ts)
— the `client` project's `include` **and** the `server` project's `exclude`. If
you change one, change both, or browser tests will also run under node and fail.

### Few, fat test files — one per category

A test file covers a whole directory and is named after it:
`components/layout/layout.browser.spec.ts` covers every component in
`components/layout/`. Colocated, so it moves with the code.

Optimise for **fewer test files, not smaller ones**. A large category spec is
fine; one spec file per component is not — it doubles the file list and buries
the component tree.

### Test the contract, not the rendering

A component test earns its place only when it guards behaviour that (a) can
break silently and (b) is not already covered by e2e. **Most components get no
test at all** — `PagePlaceholder`, `TopBar` and `Sidebar` have no contract worth
guarding.

Worth a test: `aria-current` on the active nav link; `rel="noreferrer"` on
external links. Not worth a test: that a component renders its label, or that an
`href` lands in the DOM — you would see that break instantly.

Push the weight onto pure-logic unit tests (fast, node) and e2e flows. Component
tests are the thin middle layer.

Component tests run in an actual browser, not jsdom — assert through
`page.getByRole(...)` and await the assertions:

```ts
import { page } from 'vitest/browser';
import { render } from 'vitest-browser-svelte';

render(MyComponent, { label: 'Save' });
await expect.element(page.getByRole('button', { name: 'Save' })).toBeVisible();
```

`expect.requireAssertions` is on: a test with no assertion fails.

### End-to-end tests sign in for real

[e2e/mock-api.ts](e2e/mock-api.ts) stands in for FastAPI, started by
[playwright.config.ts](playwright.config.ts) alongside the app. Tests therefore
walk the true path — form action, session creation, cookie, guard — without the
full stack, and without knowing anything about the session's internal shape.

They do need a **running Redis** (`redis://localhost:6379/15`, a throwaway
database). CI provides one as a service container.

When the config has an array of `webServer` entries, Playwright stops inferring
`baseURL`, so it is set explicitly in `use`.

## Design tokens

Defined once in [src/app.css](src/app.css). Components reference semantic names
(`bg-surface`, `text-muted-foreground`), never raw colours.

Colours are **OKLCH**, unlike the React app's HSL. OKLCH lightness is
perceptual, so `0.55` reads as the same brightness at every hue — contrast
becomes predictable and hover/muted states are derived by nudging L rather than
picking a new hex by eye.

Structure:

1. `:root` — light values on `--ow-*` variables.
2. `@media (prefers-color-scheme: dark) :root:not(.light)` — dark overrides.
3. `.dark` — same overrides again, so an explicit class beats the OS setting.
   This is the hook a manual theme toggle will use.
4. `@theme inline` — maps `--ow-*` onto Tailwind's `--color-*` so utilities are
   generated. `inline` matters: it keeps utilities pointing at the variable
   rather than baking in the resolved value.

**The set is deliberately small.** The React app has ~60 colour variables with
`-glow`/`-muted`/`-hover` variants, many unused. Add a token when a component
needs it, and add it to all three theme blocks.

## Docker

| Service            | Port | Notes        |
| ------------------ | ---- | ------------ |
| `frontend` (React) | 3000 | unchanged    |
| `frontend-svelte`  | 3001 | this project |

```bash
docker compose watch          # both frontends + backend, with sync
docker compose build frontend-svelte
```

- [Dockerfile.dev](Dockerfile.dev) — Vite dev server, driven by compose sync.
  Sets `DOCKER=1`, which switches Vite's watcher to polling (inotify does not
  fire reliably across the compose sync boundary).
- [Dockerfile](Dockerfile) — two stage, runs `bun ./build/index.js`.

### Environment

| Variable    | Purpose                                             |
| ----------- | --------------------------------------------------- |
| `API_URL`   | Backend base URL, used by the SvelteKit server only |
| `REDIS_URL` | Session store (database 2; backend uses 0, svix 1)  |

Both are **private**, read through `$env/dynamic/private`. Dynamic, never
`static`, keeps them **runtime** values, so one prebuilt image can be pointed at
any backend without a rebuild — a property the React app has and we must not
lose. Private rather than `PUBLIC_` because with cookie sessions the browser
never calls FastAPI directly; only this server does.

## Navigation

[src/lib/config/nav.ts](src/lib/config/nav.ts) is the only place destinations
are declared. `Sidebar`, `BottomNav` and `MoreSheet` all derive from it — adding
a destination means editing that array and nothing else.

Internal hrefs go through `resolve()` from `$app/paths`, which type-checks the
path against the real route tree and applies `base`. A typo becomes a build
error, not a dead link. `NavLink` and `BottomNav` carry an
`eslint-disable svelte/no-navigation-without-resolve`, because the rule cannot
see that a dynamic `item.href` was already resolved upstream.

The `primary` flag decides what appears in the mobile bottom bar. At most four:
the fifth slot is "More", and a unit test enforces that.

`navLabelFor(pathname)` is the single derivation of "which section am I in". It
feeds both the desktop header in `TopBar` and the `<title>` in
`routes/(app)/+layout.svelte`, so a new destination gets a heading and a browser
tab title without touching either file.

`TopBar` shows the **centred logotype on mobile** and the section heading on
desktop, where the sidebar already carries the brand. The bar is `h-20` below
`lg` and `h-14` above it: the logotype stacks "Open / Wearables" on two lines and
is illegible in a 56px bar. Do not swap it for the bare mark — the brand belongs
there.

### Responsive shell

`AppShell` composes the whole thing. Breakpoint is `lg` (1024px):

- **below `lg`** — sticky `TopBar` + fixed `BottomNav` (4 destinations + More).
  `MoreSheet` is a bottom sheet holding the rest.
- **`lg` and up** — fixed `Sidebar` with every destination; `BottomNav` is
  removed from the DOM, not just hidden.

Details worth preserving:

- `min-h-dvh`, never `min-h-screen` — `vh` ignores mobile browser chrome and
  leaves a gap or a scroll jump as the address bar collapses.
- `ui/Sheet.svelte` is a native `<dialog>` opened with `showModal()`, which
  supplies the focus trap, Esc-to-close, inert background and `::backdrop` for
  free. This is why `bits-ui` is not a dependency yet. It knows nothing about
  navigation — `MoreSheet` supplies the content.
- The sheet is pinned with `inset-x-0 top-auto bottom-0`. Setting both `top` and
  `bottom` (i.e. `inset-0`) stretches it to full height even with `h-auto`.
- `BottomNav`'s column count is computed from `PRIMARY_NAV_ITEMS.length + 1` via
  an inline style. A hardcoded `grid-cols-5` would leave a gap if a primary
  destination were removed, and Tailwind cannot generate a class from a runtime
  value.
- `main` reserves `4.5rem + env(safe-area-inset-bottom)` so content clears the
  bottom bar and the home indicator. An e2e test asserts they do not overlap.
- Sidebar and bottom bar carry **different** `aria-label`s (`Main` / `Primary`).
  Two landmarks with the same name is an accessibility smell.
- `LogoutButton` appears in **both** the sidebar footer and the More sheet. The
  sidebar is desktop-only, so without the sheet copy there is no way to log out
  on a phone. It is inert until auth lands — wiring it means passing an
  `onclick` at those two call sites.

### App version

The sidebar footer shows `v{version}` from `$app/environment`.
[vite.config.ts](vite.config.ts) sets `version: { name: version }` from
`package.json`; without it SvelteKit defaults to a build **timestamp**, which
would render as `v1788389600520` and look plausible enough to miss. An e2e test
asserts the string is semver-shaped.

Keep `package.json`'s version in step with `frontend/package.json` while both
frontends ship. It renders in the sidebar footer on desktop and in the More
sheet on mobile.

## Brand assets

Copied from `frontend/` — the same files the React app ships, so both frontends
look identical in a browser tab.

| Where                              | What                                                                                                        |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| [static/](static/)                 | `favicon.ico`, light/dark 16px + 32px PNGs, `apple-touch-icon.png`, `android-chrome-*.png`, `manifest.json` |
| [src/lib/assets/](src/lib/assets/) | `logo.svg` (mark only), `logotype.svg` (mark + wordmark)                                                    |

Icons are wired in [src/app.html](src/app.html), not per route — they never
change, so they belong in the static shell. Light and dark variants are selected
with `media="(prefers-color-scheme: …)"`, with `favicon.ico` as the fallback for
browsers that ignore it.

### The logos were edited on the way in

The originals carry a hardcoded `<rect fill="black"/>` background and paint
their paths `fill="white"`. That works in the React app, which is dark-only with
a black sidebar. Here it rendered as a black tile on the light theme, and even on
dark it did not match `--ow-surface`.

Both files now have the rect removed, `fill="currentColor"` on the paths, and a
viewBox tightened to the real content bounds (measured with `getBBox()`, not by
eye). They inherit the theme's text colour and can be tinted anywhere.

**If either logo is ever re-exported from a design tool, redo those three
edits** — otherwise the black tile comes back.

`Wordmark.svelte` inlines the SVG via a `?raw` import rather than using `<img
src>`, because an `<img>` cannot inherit `currentColor`. It carries a targeted
`eslint-disable` for `svelte/no-at-html-tags`: the content is a build-time asset,
never user input. Callers set the height; the SVG keeps its aspect ratio.

Not copied: `tanstack-circle-logo.png` and `tanstack-word-logo-white.svg` are
leftovers from the React scaffold. The provider marks (`garmin.svg`,
`polar.svg`, `suunto.svg`) stay in `frontend/` until a page here needs them.

## Authentication

Sessions are server-side. The browser holds **only an opaque session id** in an
`HttpOnly` cookie; the access and refresh tokens never leave this server.

```
browser --cookie: ow_session=<uuid>--> SvelteKit --Bearer--> FastAPI
                                           |
                                         Redis  ow:sess:<uuid>
```

Why, in short: `localStorage` is readable by any script on the page, so one
compromised npm dependency exfiltrates a working credential. The refresh token
matters most here — it is long-lived and, per `RefreshToken` in the backend, has
no expiry column at all, only `revoked_at`.

### Files

| File                                                                       | Role                            |
| -------------------------------------------------------------------------- | ------------------------------- |
| [src/lib/server/redis.ts](src/lib/server/redis.ts)                         | Connection, created lazily      |
| [src/lib/server/api.ts](src/lib/server/api.ts)                             | Raw calls to FastAPI            |
| [src/lib/server/session.ts](src/lib/server/session.ts)                     | Cookie + Redis record + refresh |
| [src/routes/login/+page.server.ts](src/routes/login/+page.server.ts)       | Sign-in form action             |
| [src/routes/logout/+page.server.ts](src/routes/logout/+page.server.ts)     | Sign-out action                 |
| [src/routes/(app)/+layout.server.ts](<src/routes/(app)/+layout.server.ts>) | The guard                       |

Anything under `$lib/server` can never be imported into client code — SvelteKit
fails the build if you try. That is the safety net keeping tokens off the
browser; do not defeat it by re-exporting from elsewhere.

### Things that will bite

- **The backend rotates refresh tokens.** `/token/refresh` revokes the old one
  and issues a new one, so the whole response must be persisted, not just the
  access token. Dropping the new refresh token logs the user out an hour later.
- **`ioredis`, not Bun's built-in Redis client.** Bun ships one, but the Vite
  binary carries a `#!/usr/bin/env node` shebang, so dev, preview and build all
  run server code under **node** — only production `bun ./build/index.js` is
  Bun. A Bun-only API would work in production and nowhere else.
- **The guard does not call `/auth/me` per navigation.** The developer profile
  is captured at sign-in and stored in the session. Revocation is therefore
  noticed within the access token's 60 minute life rather than instantly, which
  is the trade a short access token exists to make. A profile edited elsewhere
  stays stale until the next sign-in.
- **`readSession` fails closed.** An unreachable Redis returns null — "not
  signed in" — never a valid session.
- **The sign-in error message is identical for a wrong email and a wrong
  password.** Distinguishing them tells an attacker which accounts exist.

### The React app got this wrong — do not copy it

Worth knowing, because the old code looks authoritative:

1. `refresh_token` is never used anywhere in `frontend/src`.
2. `expires_in` is never passed to `setSession`, so it assumes a 24 hour
   session while the token dies after 60 minutes. That is the cause of the
   apparently random logouts.
3. `setSession(data.access_token, data.developer_id)` reads a field that
   `TokenResponse` does not have. Harmless only because `getDeveloperId()` is
   never called.

## Styling is scoped — do not reach for global CSS

A `<style>` block inside a `.svelte` file is scoped by the compiler. It rewrites
both selectors and `@keyframes` names with a per-component hash, so
`animation: slide-up` in `Sheet.svelte` compiles to:

```css
dialog[open].svelte-11ek6gv {
	animation: 0.2s cubic-bezier(0.32, 0.72, 0, 1) svelte-11ek6gv-slide-up;
}
```

Nothing leaks and nothing collides, so component styles never need registering
in [src/app.css](src/app.css). `app.css` is only for **tokens and base
element styles** — things that are global by definition.

Tailwind utility classes are global, but that is the point: they are generated
on demand from the class names found in source, and each does exactly one thing.

## The .json ignore trap

The **repo root** `.gitignore` blanket-ignores `*.json` (line 167) to keep
provider data dumps out of the tree, and ignores `.vscode` outright. New JSON
config here is therefore ignored **silently** — `package.json` and
`tsconfig.json` were both missing from git until this was caught.

[.gitignore](.gitignore) re-includes them; a deeper `.gitignore` wins. **Adding
a new tracked `.json` file means adding a `!` line there too.** Verify rather
than assume:

```bash
git check-ignore -v frontend-svelte/<file>    # prints the rule, or nothing
```

Re-including a file inside an ignored _directory_ needs the directory
un-ignored first — git does not descend into an excluded directory.

## Current state

```
src/
├── app.css                         # design tokens + base styles
├── app.html                        # favicons + manifest live here
├── lib/
│   ├── components/
│   │   ├── PagePlaceholder.svelte
│   │   ├── layout/
│   │   │   ├── AppShell.svelte     # composes the whole responsive shell
│   │   │   ├── AppVersion.svelte   # "Version  0.7.0" footer row
│   │   │   ├── BottomNav.svelte    # mobile bar: 4 destinations + More
│   │   │   ├── LogoutButton.svelte # inert until auth lands
│   │   │   ├── MoreSheet.svelte    # secondary destinations, mobile only
│   │   │   ├── NavLink.svelte
│   │   │   ├── Sidebar.svelte      # desktop only, lg and up
│   │   │   ├── TopBar.svelte
│   │   │   ├── Wordmark.svelte     # inlined logotype, inherits currentColor
│   │   │   └── layout.browser.spec.ts
│   │   └── ui/Sheet.svelte         # generic bottom sheet, no nav knowledge
│   ├── config/nav.ts + nav.spec.ts # single source of truth for destinations
│   └── utils/cn.ts
├── lib/server/                     # never reaches the browser
│   └── api.ts  redis.ts  session.ts + session.spec.ts
├── routes/
│   ├── +layout.svelte              # imports app.css
│   ├── +page.ts                    # redirects / → /dashboard
│   ├── login/     +page.svelte + +page.server.ts
│   ├── logout/    +page.server.ts  # action only
│   └── (app)/
│       ├── +layout.server.ts       # the auth guard
│       ├── +layout.svelte          # wraps children in AppShell
│       └── {dashboard,users,syncs,webhooks,coverage,settings}/+page.svelte
└── e2e/  auth.e2e.ts  navigation.e2e.ts  mock-api.ts  support.ts  fixtures.ts
```

Every page under `(app)` is a `PagePlaceholder`. The shell, routing, theming,
authentication and tests are real; the pages are not.

No page fetches domain data yet, so there is no browser-facing API proxy. Server
`load` functions can call FastAPI directly through `apiGet` with the token from
`validAccessToken`. A `/api/[...path]` proxy becomes necessary only when a
component needs to call the backend from the browser.

## Open decisions

Do not settle these unilaterally; they are the owner's calls.

### Data fetching

Not chosen. SvelteKit `load` + `invalidate` covers the first slices with no
dependency. `@tanstack/svelte-query` becomes justified at the first real need —
sync-status polling, optimistic updates, or a cache shared across routes. The
React app has 16 hook files built on react-query, so this will likely be
revisited; wait for the concrete trigger.

### Component primitives

`bits-ui` + `shadcn-svelte` are the equivalents of Radix + shadcn/ui, and the
component mapping is close to 1:1. Still not installed — the one overlay so far,
`MoreSheet`, is a native `<dialog>`, which already provides focus trapping and
Esc handling. `cn()` is named for the shadcn convention so the generator would
work unmodified if they are added later. Buttons, cards, inputs and
badges are plain styled elements. Add them at the first component needing real
focus management — a dialog, select, or dropdown.

## Decision log

Choices already made, with reasons, so they are not re-litigated.

- **SvelteKit over plain Svelte** — 33 route files, nested layouts, an auth
  guard and dynamic segments. Plain Svelte means bolting on a router and losing
  typed routes.
- **`adapter-node`** — matches the container deployment model. Revisit only if
  the app becomes fully static.
- **No `experimental` add-on** (async / remote functions) — moving target, and
  this project is meant to be developed slowly over months.
- **Playwright from day zero** — e2e is the safety net for deleting `frontend/`.
- **Bun** — package manager and runtime. Build still goes through Vite, so the
  gain is install and boot speed, not bundle output.
- **System font stack, not Google Fonts** — the React app blocks first render on
  a `fonts.googleapis.com` stylesheet. If the Inter brand face is wanted,
  self-host it (`@fontsource-variable/inter`) rather than reintroducing the
  external request.
- **Native `<dialog>` over a headless overlay library** — `showModal()` gives
  focus trap, Esc, inert background and `::backdrop` with no dependency.
- **Mobile navigation is a bottom bar, not a hamburger drawer** — thumb-reachable
  and always visible. The overflow sheet holds only secondary destinations.
- **Server-side sessions in Redis, `HttpOnly` cookie** over `localStorage` —
  keeps both tokens off the browser, makes SSR viable, and preserves
  "one image, any backend" by turning the API URL into a server-side variable.
  The cost accepted: the node server is load-bearing, so the dashboard can no
  longer be served as static files.
- **`cn` kept as the helper name** despite being opaque, so `shadcn-svelte` can
  generate components without edits if it is ever added.

## Baseline measurements

Taken 2026-09-02, for judging whether the rewrite is paying off. React figures
are a full application; Svelte figures are near-empty. They are not a
feature-for-feature comparison — they measure the **floor** each framework
imposes, which is the part that never goes away.

|           | React (`frontend/`)     | Svelte (foundations only) |
| --------- | ----------------------- | ------------------------- |
| Client JS | 532 KB gzip, 93 chunks  | 31 KB gzip, 9 chunks      |
| CSS       | 137 KB raw / 20 KB gzip | 9.6 KB raw / 2.8 KB gzip  |

Re-measure at parity before declaring a win:

```bash
find .svelte-kit/output/client -name '*.js' -exec cat {} + | wc -c
```
