# QueryMind — Frontend

Premium product UI for QueryMind: natural language → clarification → SQL → results.

## Stack

React 18 · Vite · React Router · Tailwind CSS · Framer Motion · Three.js / React Three Fiber · Recharts · Lucide icons

## Getting started

```bash
npm install
npm run dev       # http://localhost:5173
npm run build     # production build to dist/
npm run preview   # preview the production build
```

## Structure

```
src/
├── components/
│   ├── ui/            Button, Card, Badge, StatusDot
│   ├── navigation/     Navbar (public site), Sidebar (app shell)
│   ├── query/          QueryInput, ProcessingTimeline, SuggestionChips
│   ├── clarification/  ClarificationPanel (the ambiguity-resolution UI)
│   ├── sql/            SqlPanel (syntax highlighting, copy/explain/rerun)
│   ├── results/        ResultsTable, ResultsChart, ResultsView
│   ├── schema/         SchemaTableCard, SchemaRelationships
│   ├── history/        HistoryCard
│   ├── landing/        Hero, InteractiveDemo, TrustSection, ArchitectureDiagram, Footer
│   ├── three/          NetworkScene (R3F hero viz), HeroCanvas (WebGL/reduced-motion fallback)
│   └── layout/         AppLayout (sidebar + topbar shell)
│
├── pages/               Landing, Product, Architecture, Developers,
│                        Dashboard, SchemaPage, HistoryPage, SavedPage, SettingsPage
├── hooks/                useQueryPipeline (ask → clarify → generate state machine), useReducedMotion
├── lib/                  utils, sqlHighlight, webgl
├── services/             queryApi, schemaApi, historyApi (mock-backed, see below)
└── data/                 mockData.js — realistic sample data
```

## Connecting the real backend

Every service in `src/services/` runs on mock data out of the box so the
app is fully interactive standalone. To point it at the real QueryMind
backend (see the repo's `app/main.py`), set:

```bash
# .env.local
VITE_API_BASE_URL=http://localhost:8000
```

Then uncomment the `fetch(...)` block already left in place at the top of
`queryApi.submitQuestion` (and `schemaApi.getSchema`) — the mock fallback
and the real call are structured so swapping one line-block is all it
takes. Two things to know about today's backend:

- `POST /query` **returns** SQL + params, it does not execute the query —
  wire actual execution up on your side before trusting `result` from a
  real call.
- The backend doesn't yet capture INSERT/UPDATE values from natural
  language (see `docs/PHASE4_README.md` in the backend repo), so the
  clarification flow for writes is mocked more heavily than reads.

## Notes

- Respects `prefers-reduced-motion`: the Three.js scene falls back to a
  static gradient and skips the camera-parallax/particle animation loop.
- Falls back to a static gradient if WebGL isn't available at all.
- The `NetworkScene` (three.js) chunk is lazy-loaded so the rest of the
  app doesn't pay for it up front.
