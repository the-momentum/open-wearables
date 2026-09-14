# Svelte Frontend — Development Guide

Ground-up rewrite of the React dashboard in SvelteKit. Lives on the
`feat/svelte-frontend` branch and runs alongside the existing frontend until it
reaches parity; only then does `frontend/` get deleted.

**Status:** the foundations are done and the first real page is built. Container,
design tokens, responsive shell, cookie-backed authentication, and a complete
`/users` list. Every other destination is still a placeholder. Read "Current
state" before assuming anything exists.

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

### Invalid HTML nesting is not caught by anything here

Svelte reports it as `node_invalid_placement_ssr`, at **runtime and only in
dev**. A `<ul>` inside a `<p>` shipped once — the scope bubble inside the
provider name — and nothing caught it:

- `svelte-check` does not look at nesting.
- The browser component tests render on the client only, so an **SSR** warning
  cannot fire, and there is no hydration to mismatch.
- `svelte/server`'s `render()` in the node project emits nothing either.
- The e2e suite runs a **production build**, where the warning is stripped.

So `bun run dev` and the browser console are the only detector. Green does not
mean the markup is valid. When a component can hold caller-supplied content,
check what element it sits in: `Hint`'s bubble takes a snippet, so a `<p>`
wrapper around it is a trap.

### End-to-end tests sign in for real

[e2e/mock-api.ts](e2e/mock-api.ts) stands in for FastAPI, started by
[playwright.config.ts](playwright.config.ts) alongside the app. Tests therefore
walk the true path — form action, session creation, cookie, guard, list query —
without the full stack, and without knowing anything about the session's
internal shape.

It serves `/auth/login`, `/auth/me`, `/token/refresh`, `/token/revoke`,
`/oauth/providers` and `/users`, the last honouring `search`, `provider`,
`sort_by`, `sort_order`, `page`, `limit` and `include`. Under a user id it also
serves the detail, `/connections`, `/sync/history` and `/sync/runs`. **It rotates
refresh tokens like the real backend**, so failing to persist a rotated token
turns the suite red rather than logging users out an hour later in production.

**The suite runs on one worker, and that is not a performance oversight.**
Playwright parallelises across _files_ by default, and every file shares one
mock process whose user list is mutable and reset with `/__reset` in
`beforeEach`. With two mutating files in flight, one file's reset lands in the
middle of the other's test and the failure surfaces somewhere unrelated — a
pagination total reading 46 instead of 47. `workers: 1` in the config is what
keeps that from coming back.

Fixtures live in [e2e/fixtures.ts](e2e/fixtures.ts) — 47 users, enough for three
pages at 20 and a memorable one to search for. Add data there, not inline in a
test.

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
| [src/lib/server/auth.ts](src/lib/server/auth.ts)                           | Per-request context, memoised   |
| [src/hooks.server.ts](src/hooks.server.ts)                                 | Puts that context on `locals`   |
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

### One session read per request

`locals.auth` is a lazy, memoised context: `session()` and `accessToken()` each
resolve once per request however many loaders ask.

This matters because the layout guard and a page `load` run **concurrently** for
one render. Without memoisation that is two Redis reads and, worse, two
simultaneous refresh attempts — and since the backend rotates refresh tokens,
the second would invalidate the first.

`hooks.server.ts` was removed once as speculative, when its only two consumers
could never run together, and came back when `/users` made the overlap real.
That is the just-in-time rule working, not indecision.

### The React app got this wrong — do not copy it

Worth knowing, because the old code looks authoritative:

1. `refresh_token` is never used anywhere in `frontend/src`.
2. `expires_in` is never passed to `setSession`, so it assumes a 24 hour
   session while the token dies after 60 minutes. That is the cause of the
   apparently random logouts.
3. `setSession(data.access_token, data.developer_id)` reads a field that
   `TokenResponse` does not have. Harmless only because `getDeveloperId()` is
   never called.

## List pages

`/users` is the reference implementation. Copy its shape rather than inventing a
second one.

**State lives in the URL**, not in a component:
`?search=…&page=2&size=50&sort=name&provider=garmin&provider=oura`. The server
`load` re-runs on every change, so Back works, a filtered view is a shareable
link, and the first paint is server-rendered. No client-side data fetching,
which is why neither `@tanstack/svelte-query` nor a browser-facing API proxy
exists yet.

[users/query.ts](src/lib/users/query.ts) is the single translator between the
URL and the API. It parses defensively — a hand-edited or stale parameter falls
back to a default rather than erroring — and serialises **only non-default
values**, so a plain `/users` URL stays clean.

Two rules live in it that are easy to get wrong:

- **Changing a filter returns to page 1.** Searching from page 5 would otherwise
  land on an empty page 5 of the new result set.
- **Changing the page size does not.** `withPageSize` recomputes the page to keep
  the first visible row visible: rows 81–100 at 20 per page become page 2 at 50
  per page. Resetting to page 1 discards the reader's place, which matters most
  on exactly the deep pages where anyone bothers to change the size.

### The history rule

Getting this wrong is invisible until someone tries to leave a search.

| Interaction                       | Navigation                                           | Why                                                    |
| --------------------------------- | ---------------------------------------------------- | ------------------------------------------------------ |
| Pagination, sorting, filter chips | plain `<a href>`, so `pushState`                     | A deliberate click; Back should undo it                |
| Applying the provider panel       | `goto()`, so `pushState`                             | Same, but the selection is assembled first             |
| Typing in the search box          | `goto(..., { replaceState: true })`, debounced 300ms | Otherwise eight characters leave eight history entries |

`ui/SearchField.svelte` owns both the debounce and `replaceState` so no future
list can get it wrong. SvelteKit aborts a superseded navigation, so a slow
response cannot overwrite a newer one.

An e2e test guards this by typing three characters **slower** than the debounce,
so each really navigates, then asserting that one Back leaves the page entirely.
With `pushState` it would take three.

**Never default a list to `sort=last_synced_at`.** It is the one sort that makes
the backend aggregate across all matched users before `LIMIT`; fine as a
deliberate choice, wasteful on every render. `created_at desc` is the default.

### What is generic and what is not

| Generic — reuse                                                             | Users-specific       |
| --------------------------------------------------------------------------- | -------------------- |
| `lists/types.ts` — `Page`, `Paginated<T>`, `SortOrder`                      | `users/types.ts`     |
| `lists/pagination.ts` — page window, `PAGE_SIZES`, `pageForSize`            | `users/query.ts`     |
| `ui/Pagination`, `ui/PageSizeSelect`, `ui/SearchField`, `ui/SortableHeader` | `users/avatar.ts`    |
| `ui/FilterChip`, `ui/ToggleChip`, `ui/CopyableId`, `ui/Sheet`               | `components/users/*` |

The `ui/` components take an `hrefFor` callback rather than a query object, so
they know nothing about users.

`users/query.ts` is deliberately **not** generalised yet: parsing, omitting
defaults from the URL, and resetting to page 1 when a filter changes are all
generic concerns, but one example is not enough to fix the shape. Generalise
when the second list page lands and the two can be compared.

### Filters

Provider filtering is one control at every width: a `Provider` button with a
count, opening `ui/Sheet` — a bottom sheet on a phone, a centred panel from
`sm` up. Inline chips were tried first and abandoned: the backend enables up to
fourteen providers, which wraps into several rows on a phone and eventually on a
desktop too.

**The provider list is never hardcoded.** It comes from
`GET /api/v1/oauth/providers?enabled_only=true`, fetched alongside the users in
the same `load`. The query layer treats provider names as opaque strings, so
nothing in `src/` needs updating when the backend gains a provider.

Inside the panel the chips are **buttons that build a local draft**, applied by
an `Apply` button. They used to be links, which navigated on every click and so
closed the panel — picking three providers meant three round trips and three
reopenings. The draft also means one navigation instead of three.

Selected providers appear as removable chips under the toolbar, because the
panel hides them once closed. `SelectedProviders` falls back to the raw name for
a provider the backend no longer returns, so a filter can never become
invisible-but-active.

### Pagination

The same bar renders **above and below** the list, so the page size can be
changed without scrolling past a full page of rows. Both are `<nav>`s, given
distinct labels ("Pagination above the list" / "…below the list") — two
identically named landmarks is an accessibility smell, and it also makes every
control ambiguous to `getByRole`. Tests use the `pager()` helper in
[e2e/support.ts](e2e/support.ts) to scope to the lower one.

`paginationItems` computes the number window; a gap that would hide a single
page renders that page instead, since "1 … 3 … 5" spends an ellipsis to hide one
number. Numbers appear from `sm` up; below that the bar keeps a plain `2 / 5`
counter.

Page size is a native `<select>`, not a row of links: it collapses to one
control on a phone and hands over to the OS picker. **This is the one list
control that needs JavaScript** — a `<select>` change cannot submit on its own —
whereas paging and sorting stay plain links. Its `id` comes from `$props.id()`
because the component renders twice on the page.

`users/+page.server.ts` clamps a page past the end of the data and redirects to
the last real page. Without it a stale bookmark, or a size change made when the
list was longer, renders a dead empty page. Only the loader can do this: the
pure helper does not know the total.

### Rows open the user

There is no View action. The whole row is clickable, done without JavaScript:
the name link in `UserIdentity` carries `after:absolute after:inset-0` and the
row is `relative`, so one real link covers the row. Keyboard and screen-reader
users get an ordinary link.

Anything interactive inside the row needs `relative z-10` to sit above that
overlay — `UserActions` and `CopyableId` both do, and a test asserts that
copying the id does **not** navigate.

Row actions are edit, copy pairing link and delete, and all three work. Edit
and delete open the page-level dialogs through the `row-actions` context, so
there is one dialog per page rather than one per row.

`pairingLink()` builds `/users/{id}/pair` against this app's origin, which is a
real page — see "The pairing pages are public".

### Shared styling, not copied styling

Two extractions exist because the same classes had been pasted more than once:

- **`ui/chip.ts`** — `FilterChip` (a link, `aria-current`) and `ToggleChip` (a
  button, `aria-pressed`) differ only in element and ARIA. The class string
  lives in `chipClass()` so they cannot drift.
- **`ui/Badge.svelte`** — reach for it for any small pill. Two count pills had
  been hand-rolled instead (the provider filter's, and the scope count), which is
  how they ended up with different padding and opacity for the same thing.
- **`ui/button.ts`** — `buttonClass()`, shared by `Button.svelte` (a button) and
  `LinkButton.svelte` (an anchor). The pairing success page needs button-shaped
  links, and hand-rolling them re-declared the variant classes a third time.
  Both components **spread `...rest`**, and that is not cosmetic: the first
  `Button` took a fixed prop list and silently dropped `aria-haspopup` and
  `aria-expanded` from the provider trigger. An e2e test now asserts both.

### Mutations go through form actions

Create, edit and delete post to named actions in
[users/+page.server.ts](<src/routes/(app)/users/+page.server.ts>) — `?/create`,
`?/update`, `?/delete`. The server holds the token, so no browser-facing API
client is needed, `use:enhance` refreshes the list on success, and **the forms
work without JavaScript**.

`describe()` turns API failures into readable text — a 409 becomes "A user with
that email already exists", not the raw `detail`. `attempt()` echoes the
submitted values back into `fail()`, so a rejected form keeps what was typed.

Three things that bit while building this:

- **`enhance` resets the form on success by default**, restoring inputs to their
  _attribute_ defaults. Svelte sets the _property_, so a reopened dialog showed
  blank fields. Both dialogs pass `update({ reset: false })` and bind their
  fields to local state re-seeded on open.
- **Dialogs live once per page, not once per row** — at 100 rows the alternative
  is 200 dialogs in the DOM. `users/row-actions.ts` carries the openers down via
  context rather than threading props through list, table and card.
- **Openness is separate from the subject.** `editOpen` plus `editing` avoids the
  effect-driven syncing that a single `editing: User | null` needs to null
  itself on close.

### Shared behaviour, not copied behaviour

Extracted after the same code appeared twice or more:

| Helper                      | Replaces                                           |
| --------------------------- | -------------------------------------------------- |
| `utils/clipboard.svelte.ts` | copy-and-confirm in `CopyableId` and `UserActions` |
| `utils/forms.svelte.ts`     | the `enhance` handler in both dialogs              |
| `ui/Alert.svelte`           | the error box in both dialogs and the sign-in form |
| `requireToken` / `attempt`  | per-action token check and error handling          |

Runes only work in `.svelte` and `.svelte.ts` files — that is why the two
helpers carry the double extension.

### The provider list is cached

`fetchProviders` caches in Redis for 60s. The list is near-static, but the call
is not rare: every search keystroke, sort, page change and mutation re-runs the
loader, and `enhance` invalidates everything on success. Unlike the session
store this cache fails **open** — an unreachable Redis costs an API call, not a
login.

### Contract details that bite

- `connections` is `null` when `include=connections` was not requested and `[]`
  when the user has none. **Do not collapse that with `?? []`** — the UI renders
  `—` for the first and "No connections" for the second.
- `search` matches a pasted UUID against the id server-side, so there is no
  "looks like an id" branch in the frontend. `GET /users/{id}` must not be used
  as a substitute: it returns an unpopulated row (`last_synced_at`,
  `has_active_connection` and `connections` are always empty).
- Provider metadata (icons, display names) lives at `GET /api/v1/oauth/providers`
  and `icon_url` is relative to the **API** base. The browser cannot reach the
  API directly under cookie sessions, so provider badges are text until
  something proxies those assets.
- Parameter validation errors come back as **400**, not 422.

### Both layouts render at once

`UsersList` emits the table and the cards, hiding one with CSS, so every row is
in the DOM twice. Picking in JS would need the viewport width, which the server
does not have. Harmless at 20 rows; worth revisiting now that 100 is selectable.

It also means a bare `getByText('Zofia')` matches twice — scope list assertions
to `getByRole('table')` or to a card.

### Four CSS traps already paid for

Each of these was written, shipped into a screenshot or a red test, and fixed.

- **`sticky` inside an `overflow-x` wrapper anchors to the wrapper, not the
  viewport.** A sticky table header with `top-14` dropped onto the first row and
  silently swallowed its clicks — invisible in a screenshot, caught by a click
  test. The table header is deliberately not sticky: the page is the vertical
  scroller, so it could not work there anyway.
- **Setting both `top` and `bottom` stretches a box.** `inset-0` with `h-auto`
  fills the gap and `margin: auto` then has nothing to centre. The bottom sheet
  pins with `top-auto bottom-0`; the centred panel needs `h-fit`.
- **`min-h-*` does nothing on an inline element.** A row of size links had a box
  only around the selected one. Use `inline-flex` with a height.
- **`capitalize` lifts every word.** On `via garmin` it produces "Via Garmin";
  wrap just the value.

### ARIA on a link is not ARIA on a button

`aria-sort` and `aria-pressed` are invalid on `<a>` and `svelte-check` rejects
them. The fixes are worth copying rather than rediscovering:

| Want            | On a link                               | On a button    |
| --------------- | --------------------------------------- | -------------- |
| Sorted column   | `aria-sort` on the `<th>`, not the link | —              |
| Selected filter | `aria-current="true"`                   | `aria-pressed` |
| Current page    | `aria-current="page"`                   | —              |

## User detail page

### The layout owns the user; tabs are routes

[`[id]/+layout.server.ts`](<src/routes/(app)/users/[id]/+layout.server.ts>) is the
only place that fetches the user, so every tab shares one request. Tabs are real
sub-routes rather than a query parameter, which gives each one its **own loader**
— and that is the point, not a preference:

Connections loads four cheap indexed calls. Data Summary will load two
aggregates that scan the user's slice of `data_point_series`. As a section
inside it,
that scan would run every time anyone opened a user to check an email. As its own
route, it runs when someone asks for it.

[`src/lib/users/tabs.ts`](src/lib/users/tabs.ts) is the single source of the tab
list. [`src/params/usertab.ts`](src/params/usertab.ts) matches against the same
array, so one `[tab=usertab]` route serves every tab not built yet and an
invented slug 404s instead of rendering an empty shell. Building a tab for real
means adding its own directory, which wins over the matcher automatically.

`Women's Health` is gated on `has_womens_health_data`, which the detail endpoint
now returns directly. **Do not reach for `/summaries/data` to get it** — the
React app did, which meant the heaviest per-user aggregate in the system ran on
every page load to decide whether to draw a tab label.

### Capability flags are not the live configuration

`rest_pull`, `webhook_stream`, `webhook_ping` and `webhook_callback` come from
the **provider strategy** — what that provider can do, identical for every user.
`live_sync_mode` comes from `ProviderSetting` — how it is wired up **right now**,
and only ever `pull` or `webhook`.

Rendered as sibling badges they read as one list of equivalent facts, which made
`REST pull` and `Live: Pull` look like near-duplicates when they answer different
questions. Suunto's own strategy comment says it plainly: _"Historical sync uses
REST (rest_pull); live data via webhooks (webhook_stream)."_ — the REST flag is
about **backfill**, not live sync.

[`src/lib/connections/delivery.ts`](src/lib/connections/delivery.ts) turns them
into two sentences under two labels, `Live` and `History`. Add a capability flag
there, not as another badge.

**The wording tracks the API vocabulary, not a plain-language paraphrase.**
This is an operator's screen: `Pulled on a schedule` maps onto
`live_sync_mode: pull`, which is the thing the reader configures. A rewrite into
customer-facing prose ("We collect it from Oura on request") was tried and
rejected — it obscured the mapping without helping anyone.

The two routes share verbs so the pair reads as one story: `Pulled on a
schedule` / `Pulled on demand`, `Pushed by the provider` / `Pushed by the
provider on demand`.

**The control carries the description; there is no separate line of prose.** A
pane is a centred heading (`LIVE SYNC`, `HISTORICAL BACKFILL`) over exactly one
thing: either a real button, or a
[`StatePlate`](src/lib/components/ui/StatePlate.svelte) — button-shaped, dashed,
and a `<p>` rather than a disabled `<button>`, because a disabled control is
announced as a control that is broken, when what it actually is is information.
So a webhook-only live route reads `Pushed by the provider` in place of a button
instead of leaving half the box empty.

Where a button _does_ exist it says what it does, and the route it belongs to
moves into a [`Hint`](src/lib/components/ui/Hint.svelte) beside the heading —
along with any provider limit, which used to be a line of its own and made one
pane taller than the other. The hint toggles on click as well as hover, because
`:hover` never fires on a phone.

Two things `Hint` gets wrong if you rebuild it: it must carry **no `title`**, or
the browser draws its own tooltip with the same text on top of the bubble; and
it must reset `normal-case font-normal tracking-normal`, because it lives inside
an uppercase micro-heading and inherits it. It opens **leftwards** (`right-0`) —
every hint icon here sits in the right half of its pane, so anchoring left spilled
the bubble across the neighbouring card.

Headings are centred over their control from `sm` up. Left-aligning a heading
above a centred pair of controls read as two unrelated things. They are **not**
rotated 90°: vertical text is slow to scan, and it breaks the moment a label
gets longer.

**On a phone the pane is a row instead** — heading left, control right. Stacked
full-width panes left the card empty sideways and twice as tall as it needed to
be. The row carries `flex-wrap`, because it genuinely cannot always hold both:
the split control needs ~215px and a 390px screen leaves under 200 beside the
heading, so it drops to its own line rather than overflowing the card.

The same module decides what can be triggered, so the buttons cannot contradict
the description:

- `canSyncHistory` — either backfill route exists.
- `canForceLiveSync` — `rest_pull` **and** live sync is not webhook-driven. A
  webhook connection has nothing to pull; data arrives when the provider sends
  it. `frontend/` gates `Force Live Sync` the same way, and dropping that gate
  would offer a button that cannot do anything.

- `historyRanges` — which windows are worth offering. No cap means all of
  7/30/90/180/365, the set `frontend/` offered. A cap means everything below it
  plus the cap itself — **except** for a callback backfill, which gets only the
  cap, because `start_historical_sync` in the Garmin strategy drops `days`
  entirely and always covers its full 30. Offering 7 there would promise a
  window the backend throws away. The day that changes, deleting the
  `webhook_callback` branch is the whole fix.

Every connection gets the same select, even when it holds one option — the
control staying put is what makes the above a one-line change later.

The range and `Sync history` are **one** control, not two beside each other:
the wrapper owns the outer border and the children round only their own outer
corners. Two details matter:

- The separator is an **inset** `<span>` (`my-2 w-px`), not a `border-r`. A rule
  touching both edges cut the control in half instead of joining its halves.
- No `overflow-hidden` and no `focus-within` ring. Both were wrong: the ring lit
  the whole control when only the select had focus, and the clipping would have
  swallowed a keyboard outline. Each half now shows its own `:focus-visible`
  outline, and a mouse click on the select shows none, which is what
  `:focus-visible` is for.

**Each trigger sits under the route it triggers**: `Sync now` in the live pane,
the range and `Sync history` in the backfill pane. There is no fill behind the
panes; with controls inside them a tinted box competed with its own contents, so
a top rule and a divider carry the structure instead.

Buttons only render while the connection is `active`. Syncing stays **on the
card**: it is routine, and burying it in the menu was wrong. Only the
destructive pair lives in the menu.

On a phone the panes stack and each keeps its controls underneath. Putting them
beside the text does not fit: the History pane is a select **and** a button, and
inlining only the Live one would leave the two panes misaligned.

### One tab strip, with edges that say there is more

Eight tabs do not fit a phone. A plain scrolling strip hides most of them with
**no signal that they exist**, which is the reason a sheet-based picker was
tried first; the strip won because it keeps an adjacent section one tap away
instead of two.

The scrolling half is [`ui/ScrollFade`](src/lib/components/ui/ScrollFade.svelte),
generic because a wide table or the Data Summary calendar will want the same:

- **Gradient fades** at whichever edge has content past it, driven by a scroll
  handler rather than a breakpoint — when everything fits, both ends are reached
  and both fades hide themselves. They stop a pixel short of the bottom
  (`bottom-px`) so a rule on the scroller stays unbroken.
- Scrollbar hidden in a scoped `<style>` — Tailwind v4 has no utility, and the
  bar would sit on top of that rule.
- `scroller` is `$bindable`, which is how `UserTabs` **scrolls the active tab
  into view**: landing on `/users/{id}/scores` with the strip parked at the left
  would hide the section you just opened.

The index tab is **`Connections`**, not `Profile`: the profile is the header,
which is visible above every tab, so a tab named after it was naming the wrong
thing.

### A sync row: one colour, the rest glyphs

The status badge is the only coloured thing in a row, and everything competing
with it was turned into a muted glyph:

- **Source is an icon**, mapped in [`syncs/source.ts`](src/lib/syncs/source.ts) and
  rendered by [`SourceGlyph`](src/lib/components/syncs/SourceGlyph.svelte)
  with a fallback for a source the backend adds later. The word cost a whole
  line on a phone; the icon keeps the row to one, and the accessible name is
  still the slug's own wording (`sr-only` plus `title`).
- **Progress is a bar only while the run is moving**, and `max-w-48`. On a
  finished run it would sit at 100% saying nothing the badge has not; stretched
  across a desktop row it pulled the eye off the badge.

**The created/updated split is shared, and one source of it is still prose.**
[`SavedCounts`](src/lib/components/syncs/SavedCounts.svelte) renders
`+ 8,421 new · ↻ 12 updated` for both the backfill log and a sync row, split
rather than summed — a run that only refreshed rows it already had is a
different outcome from one that found data, and a single total hides it. Zero of
both reads `Nothing saved`, not two zeroes.

The backfill log gets the numbers as columns (`SyncRunRecord.items_inserted` /
`items_updated`). **Recent sync activity does not, yet.** The emitting task
writes them to `metadata["inserted"]`/`["updated"]` _and_ appends them to the
message
([sync_vendor_data_task.py](../backend/app/integrations/celery/tasks/sync_vendor_data_task.py)),
but `SyncRunSummary` projects `message` and drops `metadata` — so the only way
they reach the UI today is inside a sentence.

`SyncRunSummary` in [`syncs/types.ts`](src/lib/syncs/types.ts) therefore declares
`items_inserted` / `items_updated` as **optional**, and a row shows the counts
when they are present and the message when they are not. Do not parse the
message: the numbers are structured one layer up, and the fix belongs in the
schema. Both paths are covered by e2e, so adding the two fields backend-side
needs no frontend change at all.

### Chart rows share one set of column widths

[`ui/ChartRow`](src/lib/components/ui/ChartRow.svelte) owns the
label / track / value widths, and every chart row goes through it — the heatmap
rows, the ranking bars, **and the month axis**, which is a `ChartRow` with an
empty label and value. That is not tidiness: the axis has to line up with the
rows beneath it, and keeping the three widths written out in both places drifted
once already and put the month labels over the wrong columns.

Alongside it, [`ui/typography.ts`](src/lib/components/ui/typography.ts) holds
`CAPTION` (the uppercase micro heading, in four places before this) and `NOTE`
(the one-line stand-in for absent content, in three).

### Numbers are printed plainly

No thousands separator anywhere. `Intl.NumberFormat('en-GB')` renders `19,058`,
which a reader outside the anglosphere parses as a decimal. The app is
international, so counts render as bare digits.

### Recent activity filters in the browser, not on the server

The per-user `/sync/runs` endpoint takes no provider filter, so the loader reads
a window of `RECENT_WINDOW = 100` runs and the whole window goes to the client,
which narrows it and slices to `RECENT_SHOWN = 20`. Slicing to 20 first would
let a busy provider crowd a quiet one out entirely, and the filter would then
report "nothing" for a provider that did run.

**Changing the filter must not re-run the page.** Nothing needs refetching — the
window is already here — so it uses `pushState`, and that has one trap worth
knowing:

> `pushState` deliberately does **not** update `page.url`. It writes the address
> bar and sets `page.state`, but the URL SvelteKit reports stays the one the load
> was for. A `$derived` reading `page.url.searchParams` therefore never fires.

So the selection lives in `page.state.syncProvider` (declared in
[`src/app.d.ts`](src/app.d.ts)), which is what back and forward restore. The
query string is written alongside it for sharing and reload, and read **only**
on arrival, when `page.state` is empty.

Options come from **this user's connections**, not the full provider list.
[`FilterSelect`](src/lib/components/ui/FilterSelect.svelte) is the shared
control and takes an `onselect` callback rather than an href, precisely so one
caller can navigate (`PageSizeSelect`, whose value changes what the server
returns) and another can change state in place.

### The header carries the identity, not a copy of it

There is no `User information` card. A panel repeating the name, email and id of
the person already named at the top of the page was the same duplication the
React app has, so the header holds one wrapping meta line — email, id with copy,
created, last sync — and `Edit` is a pencil beside the name rather than a button
in the action row, because it edits those details.

`external_user_id` is **not displayed**. It is deprecated in the API, it means
nothing to anyone but the customer's own systems, and it was pushing the meta
line onto a second row. It lives in the edit form, which is the only place it is
useful.

The action row is `flex` without `flex-wrap`, and the identity block is
`min-w-0`: the identity shrinks so the actions stay on the name's row instead of
dropping to a line of their own. Below `sm` only the menu remains there, and the
pencil sits **before** the badge so a narrow screen wraps the badge onto its own
line rather than stranding a lone pencil.

### Actions live where their form action does

A form action resolves against **the route currently showing**, so anything in
the shared header must exist on every tab. `userActions` in
[`src/lib/server/user-actions.ts`](src/lib/server/user-actions.ts) is spread into
both the profile's `+page.server.ts` and the placeholder tab's — one line each.
The header reads its result through `page.form` from `$app/state`, because a
layout is not given `form`.

Connection actions (sync, revoke, purge) are profile-only, so they stay in the
profile's own actions.

**`attempt()` must not wrap anything that redirects.** `redirect()` throws, and
`attempt`'s catch would turn a successful delete into a 400. `delete` is written
out longhand for that reason.

### Never invent an environment variable

Customers set these in their own deployments, so a new name is a compatibility
break. **Check what `frontend/` already uses and reuse it.**

The browser-facing backend address has always been `VITE_API_URL`
(`frontend/src/lib/api/runtime-config.ts`). SvelteKit only exposes variables
matching `publicPrefix`, so the kit config sets `env: { publicPrefix: 'VITE_' }`
and `$env/dynamic/public` serves the customer's existing variable. `API_URL` and
`REDIS_URL` match neither that nor the empty private prefix, so they stay
server-only.

`VITE_API_URL` is the only variable a deployment must set — it is what a browser
or a phone dials, and the server falls back to it. `API_URL` is an optional
shortcut for the server's own hop, which is the one case where a shorter route
exists (`http://app:8000` inside Docker). The "Connect mobile app" dialog shows
`VITE_API_URL`, never `API_URL` — inside Docker that resolves to a hostname no
device can reach.

### Three sync sources, three questions

They look interchangeable and are not. Merging them into one list would silently
drop live runs older than a day.

| Question                                   | Source                      | Cost                           |
| ------------------------------------------ | --------------------------- | ------------------------------ |
| Does live sync work at all?                | `connection.last_synced_at` | free — connections load anyway |
| What ran in the last 24 hours?             | `/sync/runs` (Redis)        | one call, buffer expires       |
| When did we backfill, and did it cover it? | `/sync/history` (Postgres)  | indexed, unbounded in time     |

Only **historical** runs reach Postgres. `persist_live_sync_runs` exists on the
backend and is off deliberately — one row per webhook and per SDK batch is
hundreds a day for an active user. So the backfill panel on a provider card and
the recent-activity list are different data with different retention, and the
empty states say so rather than implying nothing ever happened.

Sync activity loads through `optional()` in the page's loader: it is reporting,
not the subject of the page, so Redis being down costs the section rather than
the whole profile. Connections and the user itself are not wrapped — without
them there is no page to render.

### Granted scopes come as one string in three shapes

`connection.scope` is whatever the provider reported, and the shapes do not
agree: space separated (`activity heartrate sleep`), comma separated (Strava's
`activity:read_all,profile:read_all`), or full URLs (Google's
`https://www.googleapis.com/auth/googlehealth.sleep.readonly`).
[`connections/scopes.ts`](src/lib/connections/scopes.ts) splits on both
separators and reduces a URL to its last path segment, which is where an OAuth
scope carries its meaning.

Rendered as small mono tags, **not** through `chipClass`: that capitalises, and
`Read:cycles` is wrong. Garmin and Suunto configure an empty scope, so an empty
list says "Not reported by the provider" rather than leaving a blank row —
nothing granted and nothing told apart.

## Data Summary

Its own route (`/users/[id]/data`) because both aggregates it needs scan this
user's slice of `data_point_series`. It fetches **two** timelines — grouped by
`series_type` and by `provider` — so switching what the rows mean costs no round
trip.

### Two heatmaps, no toggle, no ranking repeating them

`Series types` plots the types over time — `sleep stopped arriving in July while
heart rate kept coming` is the question this page answers. Providers over time
sit inside `Data collected`, beside the share bar they explain.

There is **no rows toggle**: it made one card show either dimension while a
ranking below listed the very same series types again. Each dimension has its
own section and appears once.

`Workout types` is still a ranking, because it has to be — see below.

Three things it took a rewrite to get right:

- **Cells flex; they do not scroll.** A fixed 12px cell means 90 columns always
  overflow a phone, and the first attempt did — silently, because the scroller's
  child shrank while its own children overflowed a descendant, so `scrollWidth`
  never grew and the strip was simply clipped.
- **No gaps between cells.** 90 columns of 2px gaps come to 178px, most of a
  phone's width, and the strip slid under the totals column. Contiguous bands
  read fine — the ramp separates them.
- **The ramp is square-rooted.** Linear intensity let one busy day flatten every
  other into the palest step. Step 0 is the border colour, not the surface, so an
  empty bucket reads as a bucket with nothing in it rather than a hole.

### Only the period touches the server

The period changes what the API aggregates, so it navigates — with
`noScroll`/`data-sveltekit-noscroll`, because throwing the reader back to the
header on a date change is not a page load anyone asked for.

**Everything else is a view over data already here.** Both timeline groupings
are fetched up front, and the provider filter is computed from `by_provider`, so
the row toggle and the provider filter use
[`shallowParam`](src/lib/utils/shallow.svelte.ts) — the extracted form of the
`pushState` pattern, now used three times. An e2e test asserts no `__data.json`
request follows the toggle, which is what "no round trip" actually means.

Both are [`Segmented`](src/lib/components/ui/Segmented.svelte) controls — one
recessed track with a raised active segment — not rows of loose chips, which is
what they were and what made them read as noise. It takes links (the period,
which navigates) or buttons (the provider, which does not), so the heatmap's row
toggle uses the same component. The two date inputs share one bordered box with
no borders of their own, so the pair reads as a single field.

Both filters sit **outside the cards** in
[`SummaryFilters`](src/lib/components/summary/SummaryFilters.svelte): they govern
every card, and a control tucked inside one is a control nobody finds. The
provider filter started life as the share-bar legend on the argument that a
second list of the same names would be duplication — it was, but it was also
undiscoverable, which is worse. The legend is a legend again.

### Period is All time / Day / Range, like `frontend/`

`?from=…&to=…` inclusive; both absent is all time, equal is a day. `parsePeriod`
sorts an inverted pair and ignores anything that is not a date, so a hand-edited
URL cannot ask for nothing. `periodBucket` switches to weeks past 120 days.

A single day has one column, which is not a timeline, so `plottable()` sends
those panels to `CountRanking` instead — bars, no month axis, no colour ramp.
The summary is already scoped to the period, so the bars need no extra fetch.

### The provider filter lists connections, not the period's providers

Deriving it from `summary.by_provider` made it **vanish and reappear** as the
period changed: a single day with one provider's data has one entry, so the
control disappeared. It reads `fetchConnections` instead, which is stable
whatever the period holds — and a connected provider with nothing this month is
exactly what an admin wants to be able to select. With one connection there is
nothing to choose, so the group is not rendered at all.

### What the workout heatmap needs from the backend

There is no workout-type timeline to draw. `TimelineGroupBy` is
`provider | series_type`, and `TimelineMetric` has one member, `data_points` —
its own docstring says "Event records (workouts, sleep) join as their own
metric", which is a plan, not an endpoint. `event_record` has the same shape
(`data_source_id` to join, `start_datetime` to bucket on), so the ask is a
`workout_type` grouping and an events metric. Until then `Workout types` is a
ranking and says why.

### Every panel is narrowed or labelled — never silently neither

With a provider chosen:

| Panel             | Behaviour                                                                           |
| ----------------- | ----------------------------------------------------------------------------------- |
| Totals            | narrowed from `by_provider`                                                         |
| Share bar         | keeps both segments, **dims the others** — it still answers "how big is this slice" |
| Provider timeline | filtered to that one row                                                            |
| Series types      | drops to totals from `series_counts` — the timeline takes no provider **yet**       |
| Workout types     | unchanged, and says "Across every provider"                                         |

The first version narrowed only the totals, so three panels showed every
provider's data under a heading naming one. If a panel cannot follow the filter,
its description has to say so.

The heatmaps also state **what they count**: the timeline endpoint counts
`data_point_series` rows only, so workouts and sleep are in the totals above and
not in any band.

### The one backend change worth asking for first

Series types **should** stay a heatmap when a provider is chosen. It cannot,
because the timeline endpoint has no `provider` parameter — and that gap is far
smaller than it sounds. `get_user_timeline_counts`
([data_point_series_repository.py:524](../backend/app/repositories/data_point_series_repository.py#L524))
already joins `DataSource` and filters `DataSource.user_id`; a provider filter is
one more `filter(DataSource.provider == provider)` on the same query — no new
join, no new index, no change to the response shape.

`/users/{id}/timeseries` is not an alternative: raw samples, cursor paged at 100
a time, and no provider filter either.

When that parameter lands, the fallback comes out and `Series types` plots the
chosen provider directly. The workout-type metric is the larger ask; this one is
a line.

### Month labels thin themselves out

A year of weekly columns has twelve month starts, which on a phone collide into
one smear. `MonthAxis` keeps every third start at any width and reveals the rest
from `sm` up, unless there are four or fewer, in which case they all stay.

### A derived span must keep the API's own bucket dates

`toRows` aligns a week grid to Monday only for a window the **caller** chose.
Dates that came back from the API are already on the backend's boundary, and
snapping them again shifts every key so nothing matches — which is exactly what
happened: the all-time view rendered every count as zero, and it took a mobile
screenshot to notice, because the layout was perfect. A unit test now covers it.

### Granted scopes are a count, not a row

`connection.scope` is one string, and the shapes do not agree: space separated
(`activity heartrate sleep`), comma separated (Strava's
`activity:read_all,profile:read_all`), or full URLs (Google's
`https://www.googleapis.com/auth/googlehealth.sleep.readonly`).
[`connections/scopes.ts`](src/lib/connections/scopes.ts) splits on both
separators and reduces a URL to its last path segment, where an OAuth scope
carries its meaning.

It renders as a **count beside the provider name**, with the list behind a
hover-or-tap bubble. A row under the name cost every card its height for
something only read when data is missing. `Hint` grew a `trigger` snippet and an
`align` prop for this rather than the bubble mechanics being written twice, and
it dismisses on a `pointerdown` anywhere outside itself or on Escape — pinned by
touch, the only way out was otherwise finding the same small target again.

Garmin and Suunto configure an empty scope, so there is **no badge at all** —
`0` next to a name would read as "nothing granted" when it means "nothing
reported".

### No SSE while nothing is running

The stream is not opened on load. Each open stream costs the backend a pooled DB
connection, an anyio worker thread and a Redis pubsub connection for as long as
the tab stays open, and the React app held one on every user page regardless of
which tab was showing. The snapshot from `/sync/runs` covers the resting case;
the stream is for later, opened only when a run is actually in progress.

## The pairing pages are public

`/users/[id]/pair` lives **outside the `(app)` group**, so the auth guard never
runs on it. That is the point: whoever opens a pairing link has no account here.
Both endpoints it needs are unauthenticated backend-side —
`GET /oauth/providers` and `GET /oauth/{provider}/authorize` take no API key —
so `apiGet`'s token argument is optional and these calls pass none.

The flow, all server-side:

1. The page lists `enabled_only=true&cloud_only=true` providers.
2. A choice posts to `?/connect`, which asks the backend for an authorization
   URL and `redirect(303)`s the browser to the provider.
3. The provider returns to the backend callback, which exchanges tokens, stamps
   `last_synced_at`, kicks off a backfill, and redirects to the `redirect_uri`
   we supplied: `/users/{id}/pair/success?provider=…`.

No `fetch` from the browser and no CORS, unlike `frontend/`, which called the
API directly from the client.

### Providers are sorted here, not by the API

`GET /oauth/providers` returns them in `ProviderName` enum order — the order
they were added to the codebase (`apple, samsung, garmin, google, polar, …`),
which means nothing to a reader picking their device. `cached()` in
[`server/providers.ts`](src/lib/server/providers.ts) sorts by display name on
the way out, so every consumer — pairing list, admin filter — gets the same
order without remembering to ask.

### Two traps in this flow

**`?/connect` replaces the whole query string.** A form action is a URL, so
posting to `?/connect` from `/pair?redirect_url=…` loses `redirect_url`
entirely. It travels as a hidden field instead. This cost a failing test to
find, and it applies to every action on a page whose query string matters.

**`redirect_url` is attacker-controlled.** The pairing link is public, so anyone
can craft one, and the success page renders that value as a `Continue` link.
`safeReturnUrl` in [`users/pairing.ts`](src/lib/users/pairing.ts) admits only
`http:`/`https:` — `javascript:` would otherwise be a one-click XSS on a page
end users are told to open. It is applied **twice**: in the loader, so the page
never holds a value it could render, and again when building the success URL,
because by then it has been through a form post. It is never a redirect, always
a link the reader chooses.

### Provider logos work here, and only here

The admin pages use letter marks because the API's `icon_url` is relative to a
base the browser cannot reach under cookie sessions. This page is public and the
browser talks to the address `publicApiUrl()` returns
([`config/public-api.ts`](src/lib/config/public-api.ts) — the one place
`VITE_API_URL` is read on the client), so
[`ProviderLogo`](src/lib/components/pairing/ProviderLogo.svelte) uses the real
file — falling back to the letter mark on an `onerror` or when `VITE_API_URL` is
unset.

### What the backend still owns

- **A denied consent shows raw JSON.** The callback redirects OAuth errors to
  `/api/v1/oauth/error?message=…`, which is a JSON endpoint, not a page. The
  frontend cannot intercept it; the backend would have to accept an error URL
  the way it already accepts `redirect_uri`.
- **`authorize` does not check that the user exists**, so any UUID in a pairing
  link starts a real OAuth flow. Nothing here can validate it either: reading
  the user requires a developer token this page does not have.

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
├── app.css                          # design tokens + base styles
├── app.html                         # favicons + manifest live here
├── hooks.server.ts                  # per-request auth context into locals
├── lib/
│   ├── components/
│   │   ├── PagePlaceholder.svelte
│   │   ├── layout/                  # shell: AppShell, TopBar, Sidebar,
│   │   │                            # BottomNav, MoreSheet, NavLink,
│   │   │                            # Wordmark, AppVersion, LogoutButton
│   │   │                            # + layout.browser.spec.ts
│   │   ├── ui/                      # nothing here knows about users
│   │   │   ├── Sheet.svelte         # bottom sheet / centred panel
│   │   │   ├── Pagination.svelte    # counter, numbers, size select
│   │   │   ├── PageSizeSelect.svelte
│   │   │   ├── SearchField.svelte   # debounce + replaceState live here
│   │   │   ├── SortableHeader.svelte
│   │   │   ├── FilterChip.svelte    # link: navigates
│   │   │   ├── ToggleChip.svelte    # button: edits a local draft
│   │   │   └── CopyableId.svelte
│   │   ├── providers/               # ProviderMark — a letter mark, since the
│   │   │                            # API's icon_url is unreachable from the browser
│   │   ├── syncs/                   # provider-agnostic: SyncRunRow, SavedCounts,
│   │   │                            # SourceGlyph, RecentSyncsCard
│   │   └── users/                   # UsersList, UsersTable, UserCard,
│   │                                # UserIdentity, UserAvatar, SyncCell,
│   │                                # ConnectionBadges, UserActions,
│   │                                # ProviderFilter, SelectedProviders,
│   │                                # AddUserButton
│   ├── config/nav.ts                # single source of truth for destinations
│   ├── lists/                       # generic list plumbing
│   │   ├── types.ts                 # Page, Paginated<T>, SortOrder
│   │   └── pagination.ts            # page window, PAGE_SIZES, pageForSize
│   ├── users/                       # types.ts, query.ts, avatar.ts
│   ├── server/                      # never reaches the browser
│   │   ├── api.ts  redis.ts  session.ts  auth.ts
│   │   └── users.ts  providers.ts
│   └── utils/                       # cn.ts, datetime.ts
├── routes/
│   ├── +layout.svelte               # imports app.css
│   ├── +page.ts                     # redirects / → /dashboard
│   ├── login/    +page.svelte + +page.server.ts
│   ├── logout/   +page.server.ts    # action only
│   ├── users/[id]/pair/             # public: no session, outside (app)
│   │   └── success/
│   └── (app)/
│       ├── +layout.server.ts        # the auth guard
│       ├── +layout.svelte           # wraps children in AppShell
│       ├── users/  +page.svelte + +page.server.ts
│       ├── users/[id]/              # +layout owns the user; +page is Connections
│       │   └── [tab=usertab]/       # one placeholder for every unbuilt tab
│       └── {dashboard,syncs,webhooks,coverage,settings}/+page.svelte
└── e2e/  auth  navigation  users (.e2e.ts) + mock-api  support  fixtures
```

Every `.spec.ts` sits beside what it covers; `*.browser.spec.ts` files aggregate
a whole component directory.

**Real:** the shell, theming, cookie authentication, the `/users` list with
search, provider filters, sorting, pagination and page size, its create / edit /
delete actions, the user detail page's Connections tab — identity, connected
providers with capabilities and backfill history, and the last 24 hours of sync
activity with a provider filter — and the public pairing pages.

**Not real:** every other page under `(app)` is a `PagePlaceholder`; every user
tab other than Connections renders the shared "not built yet" placeholder; and
the Apple Health XML import is a disabled menu entry — it is a multipart S3
upload (presign, sign parts, complete or abort) and needs its own increment, not
a menu item.

Only `/users` fetches domain data, and it does so from a server `load` via
`apiGet`. There is still **no browser-facing API proxy** — a `/api/[...path]`
route becomes necessary only when a component has to call the backend from the
browser, which URL-driven lists never need.

## Open decisions

Do not settle these unilaterally; they are the owner's calls.

### Data fetching

Still not chosen, and `/users` shipped without it: a URL-driven list needs no
client cache, because the server `load` is the cache key.

`@tanstack/svelte-query` becomes justified at the first need a `load` cannot
serve — polling sync status, optimistic updates on a mutation, or state shared
between two routes. The React app has 16 hook files on react-query, so this will
likely be revisited; wait for that concrete trigger rather than the next page.

### Component primitives

`bits-ui` + `shadcn-svelte` are the equivalents of Radix + shadcn/ui, and the
component mapping is close to 1:1. **Still not installed**, and the platform has
covered every case so far: `ui/Sheet` is a native `<dialog>` (focus trap, Esc,
inert background, `::backdrop`), and the page-size control is a native
`<select>`.

`cn()` is named for the shadcn convention so its generator would work unmodified
if they are added later. Buttons, cards, inputs, chips and badges are plain
styled elements.

The trigger to reconsider is a control the platform genuinely lacks: a combobox
with typeahead, a menu needing roving focus, or a popover that must be anchored
to its trigger — the last is why the provider panel is centred rather than
anchored.

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
- **URL-driven list state** over component state — Back, shareable links and
  server-rendered first paint, and it removes the need for a data-fetching
  library on list pages.
- **Native `<dialog>` again for the provider panel** rather than a popover
  anchored to its trigger: anchor positioning is not evenly supported yet, and a
  centred panel works everywhere.
- **Draft-then-apply for the provider filter**, not navigate-per-chip, so
  several providers cost one round trip.
- **A native `<select>` for page size**, accepting that it needs JavaScript,
  because a row of links did not fit a phone and could not grow.
- **Avatar tones from a fixed six-token palette**, not a hash to hex, so avatars
  cannot break contrast or clash with the theme.
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
