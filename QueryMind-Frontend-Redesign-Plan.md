# QueryMind frontend redesign: "Neural Observatory"

> **Status: implemented 2026-10-07** (all phases except the optional Ctrl+K palette, which was not requested). Verified in headless Chrome on desktop and mobile, with reduced motion and with WebGL off; walkthrough video in `preview/querymind-redesign.webm` (git-ignored).

## Why

The current site is a stock dark-SaaS template:
- centered text, a 3D hero whose spheres sit on top of the subtitle (hard to read), a plain list of boxes for "how it works", and a card grid;
- the landing page scrolls 2,498 px with **no** scroll-driven motion.

**Goal:** a cinematic, futuristic site where scrolling *is* the product demo. The app (`/app`) gets the same look, with motion kept quick so it never gets in the way of work.

## The theme: Neural Observatory

- **Story.** Your question becomes a **beam of light** travelling through a dark observatory. Your **database is a constellation**: the 4 real tables (customers, orders, order_items, products) are stars, and the foreign keys connect them. Scrolling flies the camera along the beam's path, one pipeline stage per chapter.
- **Palette.**
  - near-black space (`base-950`, kept);
  - **electric violet** (`#8b7bff`) and **cyan** (`#5eead4`) as the core neons, both kept;
  - new **signal amber** (`#fbbf24`) used *only* for "ambiguity / needs attention", so the color means something;
  - new **hot magenta** (`#f472b6`) for results.
- **Materials.**
  - glass HUD panels with corner brackets;
  - 1 px gradient borders;
  - a soft glow;
  - a very subtle film-grain/noise texture and scanline overlay;
  - a vignette.
- **Type.**
  - Space Grotesk for display, set much larger (`clamp(48px, 9vw, 140px)`) for chapter titles;
  - JetBrains Mono, small, uppercase and widely spaced for HUD labels;
  - both fonts are already loaded.
- **Signature effects.**
  - headings "decode" out of scrambled glyphs;
  - words light up as entities get recognized;
  - SQL assembles token by token;
  - numbers count up;
  - CTAs pull magnetically toward the cursor;
  - a spotlight follows the cursor over panels.

## Landing storyboard (scroll = camera flight)

A single fixed full-screen WebGL canvas sits behind the page. The DOM chapters above it are **pinned** (sticky), and their animations are **scrubbed** by scroll position: scroll back and they rewind.

| # | Chapter (scroll length) | What you see | What moves with scroll |
|---|---|---|---|
| 0 | **Boot / Hero** (100vh) | Particle nebula with a bright core. "Ask your database." decodes in. Real engine status from `/schema` (or no chip at all; the fake "operational" chip goes). | Nebula drifts and the cursor tilts the camera. A "scroll to send a query" cue pulses. |
| 1 | **The question** (200vh) | HUD input bar | "Which region generated the most revenue?" **types itself as you scroll**; "region" and "revenue" glow as recognized entities. |
| 2 | **Your schema** (200vh) | The constellation: 4 table-stars plus FK links (the real schema) | The camera arrives. The entity words fly into their stars: *revenue* → `order_items` (quantity × unit_price); *region* → `customers.country` ("closest real column", which the extractor really does). |
| 3 | **Ambiguity** (200vh) | "What were our top 10 products?" | The word **"top" glitches and splits** (amber) into *by units sold* / *by revenue*, and a clarification card slides in: "When a question can mean two things, QueryMind asks." |
| 4 | **SQL** (200vh) | HUD code panel | The SQL assembles token by token. Parameters lock in as chips (`%s ← 'India'`). Only checks that are true at ship time are listed: "parameterized", "identifiers checked against live schema". |
| 5 | **The answer** (150vh) | Bars draw, the top number counts up | Uses **a real result captured from the demo database** at build time, labeled "example run on the demo DB". No invented numbers. |
| 6 | **Safety** (100vh) | Shield grid, with points revealed in sequence | Honest points only (see Guardrails). |
| 7 | **Live console** (natural height) | The real `InteractiveDemo`, framed as a holographic console | Normal scrolling. Smooth scroll is paused while you're typing. |
| 8 | **Launch** (100vh) | "Launch QueryMind" | Click: the stars **stretch into warp lines**, then a full-screen flash, then you land in `/app`. |

Key frame sketches:
```
 CH0 HERO                                   CH3 AMBIGUITY (pinned, mid-scroll)
┌────────────────────────────────────────┐ ┌────────────────────────────────────────┐
│ QueryMind        Product  How  Devs  ▣ │ │ ⌜ AMBIGUITY DETECTED ⌝          03/08  │
│                                        │ │                                        │
│      ·  ˚   ✦  nebula core  ✦   ˚  ·   │ │   What were our  ┌top┐ 10 products?   │
│                                        │ │                  └┬──┘ (amber glitch)  │
│        A S K   Y O U R   D A T A B A S E   │ │        ┌─────────┴─────────┐           │
│      ▸ QueryMind understands.          │ │   by units sold?      by revenue?      │
│   [ Launch QueryMind ]  [ How it works ]│ │  ⌞ QueryMind asks instead of guessing ⌟│
│            ⌄ scroll to send a query    │ │  ────────────■───────── scroll progress│
└────────────────────────────────────────┘ └────────────────────────────────────────┘
```

## Motion system

- **Smooth scroll:** **Lenis** (v1.3.26, a few KB; *the only new dependency*), on marketing pages only. Never in `/app`, and never when reduced motion is requested.
- **Pinned chapters:** a `PinnedChapter` component (sticky container plus framer-motion `useScroll({ target })`) passes a 0→1 progress value to its children. The animations use `useTransform`/`useSpring`, so nothing re-renders React on every frame.
- **3D:** one persistent `UniverseCanvas` (React Three Fiber, already installed) with:
  - an additive-blended particle shader (no post-processing dependency);
  - the schema constellation;
  - the query beam;
  - a camera that moves along a curve, reading scroll progress inside `useFrame`.
- **Text and interaction primitives (no dependencies):** `ScrambleText`, `RevealWords`, `CountUp`, `Magnetic`, `CursorSpotlight`.
- **Full-screen route transitions:**
  - warp into `/app`;
  - a quick light-sweep between marketing pages;
  - inside `/app`, a fast crossfade (≤200 ms), keyed so the sidebar doesn't remount.

## Other pages

- **Product:** a horizontal **pinned reel**. You scroll vertically and the feature cards glide sideways, each with a mini-animation (ask → clarify → SQL → chart).
- **Architecture:** the 10 stages as a vertical **light beam**. A pulse travels down as you scroll and each stage expands as it passes.
- **Developers:** a terminal panel where a real `curl POST /query` types out and the real JSON response streams back. The fake SDK/webhooks/API-keys claims go (overlaps saved Track A).

## The app (`/app`), with motion that never slows you down

- **Look:** the same HUD panels and palette, plus a slow CSS aurora behind the grid. No WebGL in the app.
- **Query input:** a command-line feel, a glowing caret and a focus pulse.
- **Processing becomes an honest "pipeline beam".** Today, stages tick at a fixed 480 ms regardless of what the backend is doing. Instead: an indeterminate beam plus a **real elapsed timer**; when the response arrives, the stages cascade to done.
- **Results:**
  - the first ~20 rows stagger in;
  - small numeric results count up;
  - the chart draws on;
  - the SQL types in fast (≤500 ms, click to skip).
- **Sidebar:** the active item has a glowing beam.
- **Optional:** a **Ctrl+K command palette** (pages, recent and saved questions).

## Guardrails

- **Accessibility:**
  - with `prefers-reduced-motion` on: no smooth scroll; scrubbed scenes become simple fades; the 3D renders one static frame; the warp becomes a crossfade;
  - all text stays in the DOM (not in the canvas), the canvas is `aria-hidden`, keyboard focus stays visible;
  - text over 3D gets a scrim, which fixes today's sphere-over-subtitle problem.
- **Performance:**
  - 3D and Lenis load **only on marketing routes**, through route-level lazy loading (also saved Track F2);
  - particles: about 10k on desktop, about 3k on mobile; `dpr ≤ 1.5`;
  - rendering pauses when the tab is hidden or the canvas is off-screen;
  - shorter pinned sections on mobile, and native touch scrolling;
  - a `?fps` overlay so you can check smoothness on your own GPU (headless numbers aren't representative).
- **No WebGL:** a CSS nebula and an SVG constellation (the existing `hasWebGL()` check).
- **Honesty (folds in saved Track A's landing items):**
  - every claim must be true when it ships;
  - safety points use only facts that exist today: parameterized SQL; identifiers checked against the live schema; writes off by default and confirmed with single-use tokens; DELETE refused; credentials server-side;
  - "Read-only transactions", "Query audit log" and "Explain" appear only after Tracks B/D/E ship;
  - example numbers come from a real run on the demo DB, labeled as such.

## Build phases (each ends with a review checkpoint)

1. **Foundation:**
   - design tokens (`tailwind.config.js`, `styles/globals.css`): neon/signal colors, display sizes, noise, scanlines, HUD corners;
   - `src/motion/*` primitives, the `SmoothScroll` provider, `PinnedChapter`, `PageTransition`, the reduced-motion plumbing;
   - lazy routes in `App.jsx`.
2. **Landing, part 1:**
   - `src/components/universe/*` (`UniverseCanvas`, particle shader, `SchemaConstellation`, `QueryBeam`, `CameraRig`);
   - chapters 0–2.

   **Checkpoint:** screenshots plus a scroll capture.
3. **Landing, part 2:** chapters 3–8, the warp launch, the new Navbar/Footer.

   **Checkpoint.**
4. **Marketing pages:** Product reel, Architecture beam, Developers terminal; transitions between pages.
5. **App restyle:** AppLayout, Sidebar, QueryInput, the pipeline beam (`ProcessingTimeline.jsx`), the clarification/SQL/results panels; optional Ctrl+K.

   **Checkpoint.**
6. **Polish:**
   - mobile pass (390×844), reduced-motion pass, WebGL-off pass, lint/build;
   - measured bundle sizes before/after;
   - CHANGELOG plus README screenshots.

`HeroCanvas.jsx`/`NetworkScene.jsx` are replaced by the universe. Unused demo data in `data/mockData.js` is removed.

## Verification

- `npm test` (new pure tests: camera-path mapping, chapter-progress math, the scramble generator), `npm run build`, `npm run lint`; the backend `pytest` stays green.
- **Headless Chrome (temp Playwright driver)** at each chapter's scroll position, desktop and mobile:
  - no console errors;
  - with reduced motion emulated, the content is static and complete;
  - with `--disable-webgl`, the fallback renders;
  - the back button works through the route transitions;
  - the live console still answers against the local backend.
- **Measured and reported:** bundle sizes before/after (today's main chunk is 750 KB and the 3D chunk 800 KB), and confirmation that `/app` loads no three.js/Lenis code.
- A scroll capture per checkpoint: a recorded video if ffmpeg can be installed in the temp driver folder, otherwise frame strips.

## Decisions (defaults used if you just say "go")

1. **Scope:** the cinematic landing and marketing pages **plus** the app restyle. *(Default: both.)*
2. **Add `lenis`** (the only new dependency). *(Default: yes.)*
3. **Fold the saved Track A landing honesty fixes into this redesign.** *(Default: yes.)*
4. **Ctrl+K command palette.** *(Default: no; add later if wanted.)*
5. **Sequencing:** the Render DB move is due **before 2026-10-23** and is independent of this work. *(Default: redesign first; you schedule the DB move.)*
