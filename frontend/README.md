# AIgriculture frontend

Next.js 14 (App Router) + TypeScript + Tailwind + MapLibre GL.
Talks to the FastAPI backend at `NEXT_PUBLIC_API_URL` (default
`http://localhost:8000`).

## Quickstart

```bash
# one-time
npm install
cp .env.local.example .env.local

# in one terminal: backend
cd ..  # back to repo root
.venv/bin/uvicorn aigriculture.api.app:app --reload --port 8000

# in another terminal: frontend
cd frontend
npm run dev
# → http://localhost:3000
```

## Scripts

| command | purpose |
|---|---|
| `npm run dev` | Next.js dev server at :3000 with hot reload |
| `npm run build` | production build |
| `npm run start` | run the production build at :3000 |
| `npm run typecheck` | `tsc --noEmit` |
| `npm run lint` | ESLint via `next lint` |

## Layout

```
frontend/
├── app/                  # Next.js App Router
│   ├── layout.tsx        # root layout (Tailwind + MapLibre CSS)
│   ├── page.tsx          # the only page (region select → results)
│   └── globals.css
├── components/           # UI components (added as the UI grows)
├── lib/                  # API client + typed wire schema
├── public/
└── (config: tsconfig, next.config, tailwind.config, postcss.config)
```
