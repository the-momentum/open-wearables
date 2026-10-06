# Svelte Frontend - Agent Guide

The developer portal: a SvelteKit admin dashboard over the FastAPI backend. It
replaced the React dashboard; comments that mention "the old dashboard" refer to
that app, which lives on only in git history.

## Hard rules

- **Svelte 5 runes only.** Runes mode is forced in `vite.config.ts`; Svelte 4
  syntax does not compile. Most material online (and model memory) is Svelte 4.
  Check <https://svelte.dev/llms-medium.txt> rather than recall.

  | Svelte 4 (never)        | Svelte 5                              |
  | ----------------------- | ------------------------------------- |
  | `export let x`          | `let { x } = $props()`                |
  | `$: y = x * 2`          | `const y = $derived(x * 2)`           |
  | `$: { effect() }`       | `$effect(() => { effect() })`         |
  | `on:click`              | `onclick`                             |
  | `createEventDispatcher` | callback props (`onsave`)             |
  | `<slot />`, named slots | `{@render children()}`, snippet props |
  | `writable()` stores     | `$state` in a `.svelte.ts` module     |

  Runes work only in `.svelte` and `.svelte.ts` files.

- **No new environment variables.** Customers set them in their deployments, so a new
  name breaks compatibility. The only ones are `VITE_API_URL`
  (required; browser-facing, also the server's fallback) and `API_URL` (optional
  server-side shortcut). Both are read via `$env/dynamic/*`, so one
  image fits any backend.
- **No dependency before the code that needs it.** Say what it buys over the
  platform. `bits-ui`, `shadcn-svelte` and `svelte-query` are deliberately absent.
- **Backend changes only when the task asks for them**, and never migrations
  unless asked. Remote databases (Railway, Hetzner, client prod) are read-only.
- **The owner commits.** Propose a conventional commit name; do not commit, push,
  or switch branches.
- **Mobile-first.** Every layout starts at phone width (390px) and must not
  scroll sideways. An e2e test enforces it.

## Commands

```bash
make frontend_verify           # from repo root: check, lint, format, unit, e2e (what CI runs)
pre-commit run --all-files     # from repo root, always all files, never a subset
bun run dev                    # :3000
bun run format                 # prettier --write
```

## Architecture

```
browser --cookie ow_session (HttpOnly)--> SvelteKit server --Bearer--> FastAPI
```

**The portal is stateless.** The session (tokens and developer profile) lives in
one `HttpOnly` cookie (`server/session.ts`), so no script on the page can read it.
Nothing needs Redis or a database, and **no new environment variable may be
required** to run it. Anything in `$lib/server` cannot be imported by client code,
and the build enforces that: never re-export around it.

- The backend **rotates refresh tokens and revokes the old one on first use**.
  `rotate()` shares one refresh between concurrent requests (and for 30s after),
  so a second request cannot sign the user out. Persist the whole response.
- `locals.auth` is memoised per request: the layout guard and page `load` run
  concurrently.
- `server/cache.ts` (`recall`/`keep`/`cached`/`forget`) is an in-process cache with
  TTLs. The e2e suite empties it via `/__e2e/reset`, which exists only with
  `OW_E2E=1` (set by `playwright.config.ts`).

**Data flow**

| Need                    | Mechanism                                                                                                                               |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Page data               | server `load` calling `$lib/server/<domain>.ts` (`apiGet`/`apiPost`)                                                                    |
| Filters, paging, period | **URL state**, parsed defensively, defaults omitted from the URL                                                                        |
| Mutations               | form actions + `use:enhance`; `attempt()`/`describe()` in `server/form.ts`; `createSubmitFlag`/`messageFrom` in `utils/forms.svelte.ts` |
| Slow secondary figures  | own `+server.ts` (`totals/`, `samples/`, `trends/`) fetched with `resource()`, so the page does not wait                                |
| Optional sections       | `optional(work, fallback)`: one failing part must not take down the page                                                                |
| Instance features       | `/config` → `fetchFeatures` in the settings layout → `data.features` (missing flag = on)                                                |

Routes: `(app)/` is behind the guard in `(app)/+layout.server.ts`. The public pages
are `login`, `logout`, `accept-invite` (its path and `?token=` are fixed by the
backend's emails) and `users/[id]/pair` (it carries no session).
User tabs and settings tabs are real sub-routes, each with its own loader, so a
heavy aggregate runs only on the tab that shows it.

**Code layout**

| Path                       | Holds                                                                   |
| -------------------------- | ----------------------------------------------------------------------- |
| `lib/<domain>/*.ts`        | pure logic and types per domain (`workouts`, `syncs`, ...), unit-tested |
| `lib/server/*.ts`          | API calls per domain, session, cache, form helpers                      |
| `lib/components/<domain>/` | that domain's components                                                |
| `lib/components/ui/`       | generic controls; they know nothing about any domain                    |
| `lib/components/events/`   | shared shell of the record tabs (`AccordionCard`, `EventTotals`, ...)   |
| `lib/charts`, `lib/utils`  | shared geometry, palette, formatting, runes helpers                     |
| `lib/testing/openapi.ts`   | reads `docs/openapi.json` for guard tests                               |

**Single sources of truth**: change the source and everything that derives from it follows.

- `config/nav.ts`: destinations, sidebar, bottom bar (at most 4 primary), titles.
- `users/tabs.ts`, `settings/tabs.ts`: tab lists, matchers, feature gating.
- `providers/devices.ts`: device type icons and labels.
- `filters/period.ts`: period parsing, windows, defaults.
- `src/app.css`: design tokens.
- Provider lists come from the API (`/oauth/providers`, `/meta/coverage`) and are
  never hardcoded. Enums the UI filters on are guarded against
  `docs/openapi.json`.

## Styling

- Tailwind v4 with semantic tokens only (`bg-surface`, `text-muted-foreground`),
  never raw colours. Tokens are `light-dark()` pairs in `app.css`, and the theme follows
  the OS or the theme cookie.
- Palette, fonts (Switzer 400/500, Fragment Mono), 1px Lucide stroke and 200ms
  motion come from the Open Wearables design system. **Its 1px corners were rejected**:
  keep our radius scale.
- Shared class strings live in `ui/button.ts`, `chip.ts`, `field.ts`, `tone.ts`,
  `typography.ts` (`CAPTION`, `HEADING`, `NOTE`, `MICRO`, `INLINE_LINK`). Reuse them;
  do not paste class strings.
- Component `<style>` is scoped. `app.css` holds only tokens and base element
  styles.
- Numbers have no thousands separator (`formatNumber`). `formatCompact` is for
  estimates only.

## Tests

| Suffix              | Runner                         | For                                                |
| ------------------- | ------------------------------ | -------------------------------------------------- |
| `*.spec.ts`         | Vitest, node                   | pure logic: parsing, formatting, derivations       |
| `*.browser.spec.ts` | Vitest, real Chromium          | component contracts (ARIA state, focus, behaviour) |
| `*.e2e.ts`          | Playwright vs production build | user flows through the real form/session path      |

- **Few, fat files.** There is one spec per directory, named after it
  (`components/settings/settings.browser.spec.ts`), and never one per component.
- **Most weight sits in unit tests and e2e.** A component test earns its place only when the
  behaviour can break silently and e2e does not cover it. Do not test that a
  label renders.
- **Guard tests** keep code and backend from drifting. `server/endpoints.spec.ts` checks every
  `/api/v1/...` literal against `docs/openapi.json`. Use `openapiEnum()` for any
  enum the UI lists.
- **E2E mock** (`e2e/mock-api.ts`, port 8787) stands in for FastAPI. Its fixtures
  live in `e2e/fixtures.ts`, never inline in a test. It mirrors real behaviour, including
  quirks like refresh rotation and `has_more` on the first page.
  - Adding an endpoint means adding a mock route with the backend's real status codes and
    `detail` strings.
  - Instance or state switches are `/__name` routes (`/__lifecycle-off`,
    `/__email-off`, `/__slow/<name>`, ...), and every one is reset in `/__reset`.
  - Tests call `/__reset` in `beforeEach` and use `signIn()`/`pager()` from
    `e2e/support.ts`.
  - `workers: 1` is required, because all files share one mutable mock.
- **Assertion traps:**
  - A regex in `getByText` matches raw whitespace, and Prettier reflows markup.
    Use a string or `\s+`.
  - Lists render as both table and cards, so scope to `getByRole('table')`.
  - A closing `Sheet` keeps its text in the DOM briefly. Use `{ exact: true }`.
  - Invalid HTML nesting is caught only by `bun run dev`. Nothing in CI sees it.
    A control inside a control is checked in `navigation.e2e.ts`.

## Clean code

- **Atomic components.** Split as soon as logic grows, and group directories into
  subdirectories when they fill. Keep derivations in pure `.ts` modules so they
  can be unit-tested.
- **Extract on the second copy**, not the third. Do not abstract on the first:
  something with one example has no shape yet.
- **Derive, never duplicate.** One source per fact, everything else computed from it.
- **Comments say why, only when the code cannot.** No file-header docstrings, no
  narration of what the next line does, no history ("used to..."). Removing
  noise comments is part of every change.
- **No dead code or speculative options.** Delete what the change made unused.
- **Match the surrounding code**: naming, idiom, density.
- **Before a change that touches many call sites**, say how many and confirm the
  pattern on one first.
- Accessibility: links use `aria-current`, buttons use `aria-pressed`, and sort state goes as
  `aria-sort` on the `<th>`. Landmarks with the same role get distinct labels. A
  warning is not `role="alert"`.

## Traps already paid for

- **Never wrap a `redirect()` in `attempt()`.** The catch turns success into a 400.
- **A form action URL (`?/x`) replaces the query string.** Carry needed params as
  hidden fields.
- **`pushState` does not update `page.url`.** Keep shallow state in `page.state`
  (`utils/shallow.svelte.ts`).
- **`enhance` resets forms to their attribute defaults.** The helpers pass
  `reset: false`, and dialogs re-seed bound state on open.
- **Actions in a shared layout header must exist on every tab route.** Spread
  `userActions` into each one.
- **Never default a list to `sort=last_synced_at`.** It aggregates every user
  before `LIMIT`.
- **Validate a `provider` URL param against the user's connections before
  forwarding it.** The API's enum would 422 the whole page.
- **Do not collapse `null` to `[]` with `?? []`.** `connections` is `null` when it
  was not requested and `[]` when there are none, and the two render differently.
- **`end_date` is sent as a full timestamp.** A bare date widens to the next
  midnight.
- **`average_speed` units differ per provider.** Do not render it.
- **`zone_offset` may be null.** In that case show UTC and say so.
- **Remote `icon_url`s are unreachable under cookie sessions.** Use letter marks,
  except on the public pairing page.
- **The root `.gitignore` ignores `*.json`.** A new tracked JSON file needs a `!`
  line in `frontend/.gitignore`. Check with `git check-ignore -v`.
- **CSS:**
  - `sticky` inside an `overflow-x` box anchors to that box.
  - A flex item needs `min-w-0` to let a child scroll.
  - Use `min-h-dvh`, not `min-h-screen`.
  - `inset-0` stretches a dialog, so pin it with `top-auto bottom-0`.

## Mandatory self review

Run it on every change before reporting done, and include the last commit when the
owner asks:

1. **Redundancy.** Look for duplicated markup, logic, class strings or constants.
   Reuse the existing `ui/` piece or extract one.
2. **Comments.** Delete narration, history and obvious ones. Keep only a non-obvious
   _why_.
3. **Components.** Split anything doing two jobs, and move derivations into tested
   `.ts` modules.
4. **Globals.** Lift repeated styles into `ui/*.ts` / tokens and repeated values
   into named constants at their single source.
5. **Tests.**
   - Every new behaviour has a test in the right tier.
   - Remove tests that only check rendering or duplicate another tier.
   - New endpoints and enums are covered by the openapi guards.
6. **Performance.** No new request that grows with a user's data on page load.
   Heavy work goes on its own route or fetch, and nothing should run sequentially that could run in parallel.
7. **Contract.**
   - Response fields are checked against `docs/openapi.json`.
   - A missing flag or field degrades gracefully.
   - A failed fetch costs only its own section.
8. **Phone width.** No horizontal scroll, and controls stay reachable at 390px.
9. **Verify.** Run `make frontend_verify` and `pre-commit run --all-files`, both green.
   Report what failed if anything did.

Report findings and fixes briefly, then propose a commit name.
