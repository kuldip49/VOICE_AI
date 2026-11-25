# Kiln & Signal — Frontend

The frontend is the browser workspace for conversations, leads, appointments, the knowledge base, analytics and business settings. It is built with React, TypeScript, Vite and Tailwind CSS.

## Run it

From the repository root, install packages once:

```powershell
cd frontend
npm install
npm run dev
```

The Vite server serves the app at `http://localhost:5173` and forwards `/api` requests to the FastAPI service at `http://127.0.0.1:8000`. Start the backend in a separate PowerShell window with `..\start-backend.ps1` from the repository root.

## Useful commands

```powershell
npm run build  # TypeScript check and production build
npm run lint   # Oxlint
npm run preview # Preview the production build locally
```

The visual system is defined in `src/index.css`; the shared navigation and workspace shell are in `src/components/layout/AppShell.tsx`. Feature pages live in `src/pages/`, and API calls are typed in `src/lib/api.ts`.
