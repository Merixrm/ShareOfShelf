# ShareOfShelf: Web Dashboard (Base44)

A Persian, right-to-left (RTL) retail-analytics dashboard for the ShareOfShelf
project. It is a React single-page app built with Vite, Tailwind CSS and shadcn/ui
components, and it runs on the [Base44](https://base44.com) platform, which provides
authentication and the backend.

Most pages show **mock data**. The **Shelf Analysis** page is live: it sends a shelf
photo to the Python detection API (`shelf_api.py` in the repository root) and shows
the real detections and share-of-shelf numbers.

---

## Contents

1. [Pages](#pages)
2. [How the app is put together](#how-the-app-is-put-together)
3. [Prerequisites](#prerequisites)
4. [Run locally](#run-locally)
5. [Environment variables](#environment-variables)
6. [Frontend only, against the hosted backend](#frontend-only-against-the-hosted-backend)
7. [npm scripts](#npm-scripts)
8. [Project structure](#project-structure)
9. [Publish your changes](#publish-your-changes)
10. [Troubleshooting](#troubleshooting)
11. [Docs and support](#docs-and-support)

---

## Pages

| Page | Route | Data source |
| --- | --- | --- |
| Dashboard | `/` | mock data |
| Distribution map | `/map` | mock data |
| Products / product detail | `/products`, `/products/:id` | mock data |
| Brands | `/brands` | mock data |
| Stores / store detail | `/stores`, `/stores/:id` | mock data |
| **Shelf analysis** | `/shelf-analysis` | **live: the Python detection API (`shelf_api.py`)** |
| Unknown products | `/unknown` | mock data |
| Opportunities | `/opportunities` | mock data |
| Reports | `/reports` | mock data |
| Settings | `/settings` | mock data |

Every route requires a signed-in user. When there is no session, the app sends the
user to the Base44 login page (`base44.auth.redirectToLogin`, called from
`src/lib/AuthContext.jsx`). The `Login`, `Register`, `ForgotPassword`,
`ResetPassword` and `OAuthConsent` files in `src/pages/` are not wired into the
router in `src/App.jsx`.

## How the app is put together

```
browser ──► web app (Vite dev server, port 5173)
              │
              ├── /api/...  ──► Base44 backend (auth, entities)     via the Base44 Vite plugin proxy
              │
              └── http://127.0.0.1:8001/api/...  ──► shelf_api.py   (Shelf Analysis page only)
```

- **Authentication** goes through the Base44 SDK. The client is created in
  `src/api/base44Client.js` and the auth state lives in `src/lib/AuthContext.jsx`.
- **Mock data** for every page except Shelf Analysis lives in `src/lib/mockData.js`.
- **Shelf Analysis** (`src/pages/ShelfAnalysis.jsx`) uploads a photo to
  `shelf_api.py`, polls for the result, draws the detected boxes on the photo, and
  shows per-SKU status and share of shelf. The API client is `src/lib/shelfApi.js`.
  It also maps the knowledge-base labels (for example `sunich_1L_apple`) to the
  Persian brand, flavour and size names used elsewhere in the app.
- **Why the detection API is called by absolute URL.** The Base44 Vite plugin
  proxies every request that starts with `/api` to the Base44 backend. A relative
  `/api/...` request would therefore never reach `shelf_api.py`, so the client
  always uses the full URL from `VITE_SHELF_API_URL`.

## Prerequisites

1. **Node.js 20.19+ or 22.12+** (required by Vite 8) and npm.
2. **Dependencies:** run `npm install` in this directory.
3. **Base44 CLI:** `npm install -g base44@latest`.
4. **[Deno](https://docs.deno.com/runtime/getting_started/installation/).** The
   local Base44 backend started by `base44 dev` runs on it.
5. **A Base44 account** with access to this app.
6. **For the Shelf Analysis page only:** the Python environment from the
   repository root (see the [root README](../README.md#installation)).

Run `base44 --help`, or see the
[CLI reference](https://docs.base44.com/developers/references/cli/commands/introduction),
for the full command list.

## Run locally

You need **two terminals**: one for the Python detection API and one for the web
app.

**Terminal 1: detection API** (from the repository root)

```bash
source .venv/bin/activate          # or whichever environment has requirements.txt installed
python shelf_api.py                # http://127.0.0.1:8001
```

The models load in the background. The first start after a knowledge-base change
can take a few minutes on CPU while embeddings are rebuilt. The Shelf Analysis page
shows an error until `http://127.0.0.1:8001/api/state` reports `"ready"`.

**Terminal 2: web app** (from `web-base44/`)

```bash
base44 login   # once per machine
base44 link    # once per clone
base44 dev     # starts the local Base44 backend and the Vite frontend together
```

Open the frontend URL that `base44 dev` prints (usually `http://localhost:5173`).

Things worth knowing:

- **Every fresh clone needs `base44 link`.** It writes `base44/.app.jsonc`, the
  pointer to your app id. That file is gitignored on purpose because it is
  per-clone. Your app id is in the Base44 Builder URL
  (`app.base44.com/apps/<id>/...`). `base44 link --help` shows the non-interactive
  flags.
- **`base44 dev` starts the frontend for you**, through `site.serveCommand` in
  `base44/config.jsonc`. Do not also run `npm run dev`: the second Vite server
  silently takes the next free port and you end up looking at the wrong one.
- **`npm run dev` on its own** serves only the frontend, with no local Base44
  backend (the console shows `[base44] Proxy not enabled` and Base44 `/api` calls
  fail). The mock-data pages and Shelf Analysis still work, because Shelf Analysis
  talks to `shelf_api.py` directly. Login needs a Base44 backend, either local
  (`base44 dev`) or hosted (`base44 dev --remote`).
- **The app must be published at least once before the UI loads under
  `base44 dev`.** The frontend starts by fetching app settings from the hosted app.
  Before the first publish that request fails and every page redirects to login.
- Under `base44 dev`, entities, functions and auth run locally, and entity data is
  **kept in memory only** (it is wiped when `base44 dev` restarts). Core
  integrations and OAuth login are forwarded to your deployed app. Full details:
  [Local development overview](https://docs.base44.com/developers/backend/overview/local-dev/local-development-overview).

## Environment variables

Put local values in `.env.local` in this directory. It is gitignored and must never
be committed. Vite only exposes variables that start with `VITE_` to the browser.

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_SHELF_API_URL` | no | Detection API base URL. Default `http://127.0.0.1:8001`. Set it when `shelf_api.py` runs on another host or port, e.g. after `python shelf_api.py --host 0.0.0.0 --port 9000` |
| `VITE_BASE44_APP_ID` | normally set for you | Base44 app id (provided by `base44 link` / `base44 dev`) |
| `VITE_BASE44_APP_BASE_URL` | normally set for you | Base44 app base URL |
| `VITE_BASE44_FUNCTIONS_VERSION` | no | Base44 functions version |

Example `.env.local`:

```bash
VITE_SHELF_API_URL=http://127.0.0.1:8001
```

## Frontend only, against the hosted backend

To work on just the frontend against your app's live hosted backend:

```bash
base44 dev --remote
```

⚠️ In this mode every write goes to your app's **production data**. Plain
`base44 dev` keeps everything local.

## npm scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Vite dev server only (no local Base44 backend; see above) |
| `npm run build` | Production build into `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` / `npm run lint:fix` | ESLint (check / auto-fix) |
| `npm run typecheck` | Type-check through `jsconfig.json` |

## Project structure

```
web-base44/
├── base44/
│   ├── config.jsonc         # Base44 project config (install/build/serve commands)
│   └── entities/            # Base44 entity schemas (User)
├── public/                  # favicons and web-app manifest, served as-is
├── src/
│   ├── main.jsx, App.jsx    # entry point and routes
│   ├── api/base44Client.js  # Base44 SDK client
│   ├── pages/               # one file per route (ShelfAnalysis.jsx is the live one)
│   ├── components/          # layout, charts, tables, map, cards
│   │   └── ui/              # shadcn/ui primitives
│   ├── lib/
│   │   ├── shelfApi.js      # client for the Python detection API
│   │   ├── mockData.js      # demo data for the other pages
│   │   └── AuthContext.jsx  # auth state
│   └── hooks/, utils/
├── index.html               # HTML shell (lang="fa", dir="rtl", Vazirmatn font)
├── vite.config.js           # Vite + Base44 plugin
├── tailwind.config.js, postcss.config.js, components.json   # styling / shadcn config
├── eslint.config.js, jsconfig.json                          # lint and type-check config
└── package.json, package-lock.json
```

## Publish your changes

After pushing your changes to git, open the Base44 dashboard and publish the app:

```bash
base44 dashboard open
```

This repository syncs to Base44 through git, so publish from the dashboard and not
with `base44 deploy`. A CLI deploy ships your local files directly and bypasses the
git sync, so the deployed app silently drifts away from what is in the repository.

## Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Shelf Analysis shows a connection error | `shelf_api.py` is not running, or is still loading. Open `http://127.0.0.1:8001/api/state` and wait for `"ready"`. |
| Shelf Analysis works on one machine but not from another device | The API listens on `127.0.0.1` by default. Start it with `--host 0.0.0.0` and set `VITE_SHELF_API_URL` to that machine's address. |
| Every page redirects to login under `base44 dev` | The app has never been published. Publish it once from the Base44 dashboard. |
| `[base44] Proxy not enabled` in the console | You ran `npm run dev` instead of `base44 dev`. |
| The page you are looking at does not show your changes | Two Vite servers are running on different ports. Stop `npm run dev` and use only `base44 dev`. |
| `base44 dev` cannot find the app | Run `base44 link` in this clone. |

## Docs and support

- GitHub integration: <https://docs.base44.com/developers/app-code/local-development/github>
- Local development: <https://docs.base44.com/developers/backend/overview/local-dev/local-development-overview>
- Support: <https://app.base44.com/support>
