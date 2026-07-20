# AI Email Assistant — Chrome Extension

Side-panel UI over the FastAPI backend in `../backend`. See
[`../docs/architecture/frontend-plan.md`](../docs/architecture/frontend-plan.md)
for the full design and build order.

## Run it

```bash
npm install
npm run dev          # writes dist/ and watches
```

Then load it in Chrome:

1. `chrome://extensions` → enable **Developer mode**
2. **Load unpacked** → select `frontend/dist`
3. Open <https://mail.google.com> and click the toolbar icon

`npm run build` produces the same `dist/` without the watcher.
`npm run typecheck` runs `tsc` alone.

The backend must be running for anything beyond step 1:

```bash
cd ../backend && uv run uvicorn src.main:app --reload
```

## Scripts

| Command | Purpose |
|---|---|
| `npm run dev` | Vite dev server + HMR, writes `dist/` |
| `npm run build` | Typecheck, then production build |
| `npm run typecheck` | `tsc --noEmit` |
| `python scripts/make_icons.py` | Regenerate `public/icons/` placeholders |

## Version pins — read before upgrading

This project runs on **Node 18.17.1**, which constrains three packages. All
three are pinned deliberately; bumping any of them without also upgrading Node
breaks the build, in two cases with an error that does not mention Node at all.

| Package | Pin | Why |
|---|---|---|
| `tailwindcss`, `@tailwindcss/vite` | `~4.1.18` | `@tailwindcss/oxide` 4.2.0+ requires Node ≥ 20. npm skips the platform binary as an unmet optional dependency, and the build fails with **"Cannot find native binding"** — which reads like an npm bug, not a Node version problem. |
| `@vitejs/plugin-react` | `^4.7.0` | v5.0.0+ requires Node ≥ 20.19. |
| `vite` | `^6.4.3` | v7 requires Node ≥ 20.19. |

`@crxjs/vite-plugin` is on stable `2.7.1` and supports Vite 3–8, so it is not a
constraint either way.

**On Node 20+**, all three pins can be dropped to `latest` in one commit.

## Layout

```
src/
├── background/     MV3 service worker — alarms, badge, notifications
├── content/        Gmail page only; reads the open thread's sender
├── sidepanel/      the product: React root + app shell
└── styles/         Tailwind entry
```

Two rules the architecture depends on:

- **Never use axios in `background/`.** Axios's browser build needs
  `XMLHttpRequest`, which does not exist in a service worker. The panel uses
  `services/http.ts` (axios); the worker uses `services/fetchClient.ts` (fetch).
- **Never use `setInterval` in `background/`.** MV3 terminates the worker after
  ~30s idle. Recurring work uses `chrome.alarms`, which has a ~1 minute floor.
