# PPE Guardian &bull; Frontend Dashboard

PPE Guardian is a real-time computer vision dashboard for monitoring Personal Protective Equipment (hard hats / helmets and high-visibility safety vests) compliance in industrial and construction worksites. It connects to the FastAPI backend service to ingest images, live camera feeds, and video files, visualizing detected workers and safety infractions with clear bounding box overlays.

---

## Prerequisites

- **Node.js**: Node 20 or newer (validated on Node 20+)
- **Operating System**: Windows (PowerShell commands documented below), macOS, or Linux
- **Package Manager**: npm (ships with Node.js)

---

## Getting Started (Windows PowerShell)

Run these commands inside the `frontend/` directory:

```powershell
# 1. Install dependencies
npm install

# 2. Copy the environment configuration template
Copy-Item .env.example .env

# 3. Start the local Vite development server
npm run dev
```

Open your browser at **[http://127.0.0.1:5173](http://127.0.0.1:5173)**.

---

## NPM Scripts

| Script                 | Command                | Purpose                                                                          |
| :--------------------- | :--------------------- | :------------------------------------------------------------------------------- |
| `npm run dev`          | `vite`                 | Starts the Vite dev server bound to `127.0.0.1:5173`                             |
| `npm run build`        | `tsc -b && vite build` | Type-checks code with TypeScript and creates production bundle in `dist/`        |
| `npm run preview`      | `vite preview`         | Previews the production build locally                                            |
| `npm run lint`         | `eslint .`             | Runs ESLint with TypeScript and React Hook rules                                 |
| `npm run typecheck`    | `tsc -b --noEmit`      | Validates TypeScript types strictly across the whole project without emitting JS |
| `npm test`             | `vitest run`           | Executes all Vitest unit and integration test suites once                        |
| `npm run test:watch`   | `vitest`               | Runs tests in interactive watch mode for active development                      |
| `npm run format`       | `prettier --write .`   | Automatically formats all TypeScript, TSX, CSS, and JSON files                   |
| `npm run format:check` | `prettier --check .`   | Checks formatting compliance in CI/CD without modifying files                    |
| `npm run gen:api`      | `openapi-typescript`   | Regenerates TypeScript types from backend OpenAPI contract (`docs/openapi.json`) |

---

## Authentication

### Token Storage Architecture & Trade-Offs

- **Access Token (In-Memory)**: Kept in memory only (`src/lib/tokenStorage.ts`). Short-lived (15 minutes). Never written to `localStorage` or `sessionStorage` to mitigate token theft via persistent disk extraction.
- **Refresh Token (`localStorage`)**: Stored in `localStorage` under key `ppe.refresh_token`. Longer-lived (7 days).
- **Trade-Off**: `localStorage` is accessible to scripts running in the same origin and is therefore susceptible to Cross-Site Scripting (XSS). For an enterprise production environment, backend-managed `HttpOnly`, `Secure`, `SameSite=Strict` cookies are recommended. For this dashboard hackathon/project setup, `localStorage` provides a resilient and straightforward mechanism for session persistence without cookie domain coordination.

### Single-Flight Token Refresh

The backend rotates refresh tokens on every refresh call and rate-limits the endpoint to 10 requests per minute. If multiple API requests fail with HTTP 401 concurrently, the response interceptor in `src/api/client.ts` uses a **single-flight** promise. All failed requests await the exact same refresh promise, preventing race conditions, duplicate rotation invalidations, and 429 rate limit errors.

### Request Format

- **Login (`POST /auth/login`)**: Takes `application/x-www-form-urlencoded` with fields `username` and `password`. The `username` form field accepts either the user's username or their registered email address.
- **Registration (`POST /auth/register`)**: Takes JSON `{ email, username, password }` and returns HTTP 201 with the created `UserOut` schema.
- **Refresh (`POST /auth/refresh`)**: Takes JSON `{ refresh_token }` and returns a newly rotated token pair.

### Demo Credentials

When running with mock data enabled, the following demo account is available:

- **Username**: `demo` (or email: `demo@example.com`)
- **Password**: `Demo@1234`
- **Role**: `user`

### Switching to the Real Backend

1. Ensure the FastAPI backend server is running on `http://127.0.0.1:8000`.
2. Edit `frontend/.env` (or create it from `.env.example`):
   ```env
   VITE_API_URL=http://127.0.0.1:8000
   VITE_WS_URL=ws://127.0.0.1:8000
   VITE_USE_MOCKS=false
   ```
3. Restart the Vite development server (`npm run dev`).
4. **CORS Requirement**: The backend server must allow `http://127.0.0.1:5173` in its `ALLOWED_ORIGINS` setting.

### Updating API Types

Whenever the FastAPI backend routes or Pydantic models are modified:

```powershell
npm run gen:api
```

This regenerates `src/api/generated/schema.ts` from `docs/openapi.json`. Domain types (`Token`, `UserOut`, `UserCreate`, `RefreshRequest`) are re-exported through `src/api/types.ts`.

---

## Folder Structure

```
frontend/src/
├── app/                  # Application routing, global context providers, and layout shells
│   └── layouts/          # Persistent layout wrappers (AppLayout for dashboard, AuthLayout for login)
├── api/                  # Unified backend HTTP and WebSocket communication layer
│   ├── endpoints/        # Feature-specific typed API query and mutation hooks
│   └── generated/        # Auto-generated TypeScript types matching backend OpenAPI schemas
├── mocks/                # Development and test mock system
│   └── fixtures/         # Static fixture data matching backend schemas for offline development
├── features/             # Modular business-domain feature modules
│   ├── auth/             # Authentication token state, login forms, and session persistence
│   ├── analyze/          # Image upload dropzone, inference dispatch, and parameter controls
│   ├── results/          # Inspection batch viewer, result summaries, and detailed inspection views
│   ├── workers/          # Workforce directory, compliance scorecards, and gear assignment
│   ├── violations/       # Non-compliance event log, incident filters, and acknowledgment actions
│   ├── video/            # Recorded video stream playback and timestamped infraction markers
│   ├── alerts/           # Real-time WebSocket violation alert notifications and toast dispatch
│   ├── evaluation/       # Benchmark metric visualizations and model accuracy diagnostics
│   └── reports/          # Shift compliance summaries, audit exports, and report generators
├── components/           # Reusable user interface components
│   ├── ui/               # Core design system primitives installed via shadcn CLI
│   └── common/           # Shared application-level composite components (PageHeader, AppBackground, PlaceholderCard)
├── hooks/                # Cross-cutting custom React hooks for browser APIs and local UI state
├── lib/                  # Shared utility functions, design token helpers, and validated env config
├── pages/                # Top-level route view components rendered by the router
├── styles/               # Global CSS files, design tokens, and semantic verdict colors
└── test/                 # Test setup configuration, test utilities, and suite specifications
```

---

## How the Frontend Connects to the Backend

The frontend follows five strict architectural rules for backend integration:

1. **One API layer in `src/api`**: Pages and components never call browser `fetch` directly. Every network request is mediated through typed API functions in `src/api`.
2. **API types are generated from `docs/openapi.json`**: All payload schemas, query parameters, and response structures are generated directly from the backend's OpenAPI contract to guarantee end-to-end type safety.
3. **Mock mode (`VITE_USE_MOCKS`) lets us build without the backend**: When `VITE_USE_MOCKS=true`, the API layer returns realistic mock data from `src/mocks/fixtures/`, enabling complete UI development and testing independent of the FastAPI service.
4. **The PPE result contract is validated before use**: Detections, bounding boxes, labels (`helmet`, `vest`), and worker associations are validated against expected schemas before being consumed by rendering canvases or tables.
5. **All URLs come from env variables**: Host addresses, API base paths (`VITE_API_URL`), and WebSocket endpoints (`VITE_WS_URL`) are read exclusively through `src/lib/env.ts` with strict defaults (`127.0.0.1:8000`).

---

## Page Background Architecture Note

> **CRITICAL**: The page background lives **only** in `src/components/common/AppBackground.tsx`. It will be replaced later with a custom image or gradient; every other component must **not** set a full-page background. All surface components (cards, sidebar, topbar) use slightly translucent styling (e.g. `bg-card/90` with subtle backdrop blur) to maintain contrast and legibility over future background wallpapers.

---

---

## UI Kit

The frontend includes a reusable, accessible design component kit built with Tailwind CSS, Lucide icons, and Radix UI primitives:

- **`VerdictBadge`** (`src/components/common/VerdictBadge.tsx`): Displays PPE compliance verdicts (`compliant`, `violation`, `uncertain`) with semantic F1 color tokens, accessible icons, and custom label overrides.
- **`VerdictLegend`** (`src/components/common/VerdictLegend.tsx`): Explains the three compliance categories along with their human-readable definitions.
- **`Spinner`** (`src/components/common/Spinner.tsx`): Animated spinning indicator with accessible hidden text and `sm`/`md`/`lg` sizing.
- **`LoadingState`** (`src/components/common/LoadingState.tsx`): Centered spinner and message with `role="status"` and `aria-live="polite"` for asynchronous views.
- **`CardSkeleton`** (`src/components/common/CardSkeleton.tsx`): Skeleton placeholder matching stat and panel card layout.
- **`TableSkeleton`** (`src/components/common/TableSkeleton.tsx`): Skeleton placeholder for tabular data with configurable rows and columns.
- **`EmptyState`** (`src/components/common/EmptyState.tsx`): Zero-data placeholder displaying an icon, title, explanatory copy, and recovery action button.
- **`ErrorState`** (`src/components/common/ErrorState.tsx`): Accessible error presentation (`role="alert"`) supporting `card` and `inline` variants, copyable request reference IDs, and retry actions.
- **`StatCard`** (`src/components/common/StatCard.tsx`): KPI metric card featuring semantic verdict accent borders/tones and loading skeleton states.
- **`ConfirmDialog`** (`src/components/common/ConfirmDialog.tsx`): Accessible Radix confirmation modal supporting asynchronous pending states, spinner indicators, and automatic error toast dispatch.
- **`notify`** (`src/lib/notify.ts`): Typed notification wrapper over Sonner for consistent success, info, warning, error, and `apiError` toast alerts.
- **`PageHeader`** (`src/components/common/PageHeader.tsx`): Standardized page header supporting status badges and responsive actions slots.
- **`ErrorBoundary`** (`src/components/common/ErrorBoundary.tsx`): React class component boundary isolating page render failures to preserve sidebar and navigation integrity.
- **`RouteErrorPage`** (`src/pages/RouteErrorPage.tsx`): Top-level React Router error element catching navigation and routing exceptions.

### Interactive UI Showcase (Development Only)

In development mode (`npm run dev`), open **[http://127.0.0.1:5173/dev/ui-kit](http://127.0.0.1:5173/dev/ui-kit)** to inspect and test all components, badge variants, loading states, error states, and async dialog flows. The showcase is lazy-loaded and omitted from production builds.

---

## Development Roadmap

- [x] **Step F1**: Scaffold, app shell, design tokens, tests
- [x] **Step F2**: API layer + auth + mocks
- [x] **Step F3**: UI kit
- [ ] **Step F4**: Analyze page _(needs backend patch BP1 first)_
- [ ] **Step F5**: Annotated result
- [ ] **Step F6**: Workers page _(needs BP2)_
- [ ] **Step F7**: Violations page _(needs BP3)_
- [ ] **Step F8**: Realtime alerts + siren
- [ ] **Step F9**: Video clips _(needs BP4)_
- [ ] **Step F10**: Results page
- [ ] **Step F11**: PDF report
- [ ] **Step F12**: Live webcam
- [ ] **Step F13**: Polish
