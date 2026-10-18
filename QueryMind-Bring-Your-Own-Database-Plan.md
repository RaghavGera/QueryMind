# QueryMind: accounts and bring your own database (plan)

> **Status: approved scope, not started (2026-10-18).** The decisions below were made by the owner. Work goes phase by phase; each phase ends with tests, a live check, and a commit message for the owner.

## Decisions

| Topic | Decision |
|---|---|
| Accounts | Required for the whole app. **Sign in with Google**, implemented by us: the frontend uses Google Identity Services and FastAPI verifies Google's signed ID token. Users are stored in Neon. |
| Who can sign in | Anyone with a Google account |
| Session | The API issues its own signed, expiring session token, sent as `Authorization: Bearer`, plus a Content-Security-Policy on the site |
| Usage limits | **20 questions per user per day** (every `/query` call counts, including clarification answers). Visitors who aren't signed in get **3 free tries per day** in the landing console, then "Sign in with Google to keep going". |
| History and saved queries | Stored per account in Neon and synced across devices. Existing browser entries are imported on first sign-in. |
| Data sources | Both **file uploads** (CSV / Excel) and **connecting your own PostgreSQL** |
| Connection credentials | Encrypted on the server (Fernet), deleted after 24 hours |
| Writes on uploaded or connected data | **Never.** Read-only, enforced by read-only transactions. Writes stay demo-only. |
| New dependencies | `openpyxl` (Excel), `cryptography` (credential encryption), and probably `PyJWT` (token signing/verification; confirm before adding) |
| Engines | PostgreSQL first |

## Owner actions (things only you can do)

1. **Google Cloud: create an OAuth client ID** (type "Web application").
   - Authorized JavaScript origins: `https://query-mind-tawny.vercel.app` and `http://localhost:5173`.
   - Set up the OAuth consent screen with scopes `openid`, `email`, `profile`. A privacy-policy link is needed to publish; Phase 1 adds a Privacy page for it.
2. **Render environment:**
   - `GOOGLE_CLIENT_ID`;
   - `SESSION_SECRET`, a long random string that signs session tokens;
   - `CREDENTIAL_KEY` (Phase 6), the Fernet key that encrypts stored connection URLs.
3. **Vercel environment:** `VITE_GOOGLE_CLIENT_ID`.

Never paste these values into chat; use the dashboards' environment screens.

## Phases and steps

### Phase 1: accounts and usage limits
1. **Tables** in `querymind_meta`, created at startup:
   - `users`: Google subject id, email, name, avatar, created_at, last_login;
   - `sessions`: id, user, expiry, revoked; supports sign-out;
   - `usage`: per user per day, plus hashed-IP anonymous counters.
2. **`POST /auth/google`.** Verifies the Google ID token:
   - signature against Google's published keys;
   - audience equals our client id;
   - issuer is Google;
   - not expired;
   - email verified.

   It then upserts the user and returns a session token (7-day expiry).
3. **More endpoints:** `GET /auth/me` returns the user plus today's usage (`used`, `limit`, reset time). `POST /auth/logout` revokes the session.
4. **Authorization:**
   - `/query`, `/query/confirm` and the new APIs require a session.
   - **Exception:** `/query` without a session is allowed on the demo workspace only, at 3 per day per visitor.
   - **Limits:** a 21st question returns 429 with a clear message ("You've used today's 20 questions; they reset at 00:00 UTC").
5. **Frontend:**
   - a sign-in page with the Google button;
   - an auth context, with the token kept in memory and in `localStorage`;
   - `/app/*` redirects to sign-in when not signed in;
   - an account menu (avatar, "12 / 20 questions today", sign out);
   - the landing console shows "2 free tries left today", then a sign-in prompt.
6. **Security headers:** a Content-Security-Policy in `frontend/vercel.json` that allows only our scripts plus Google's sign-in, and a Privacy page.

### Phase 2: history and saved queries in the account
7. Add `query_history` and `saved_queries` tables keyed by user, storing the same snapshot shape as today: SQL, params, warnings, up to 200 rows.
8. Add CRUD endpoints. The frontend `historyApi` / `savedApi` switch to them, with the same UI behaviour: Reopen without re-running, Re-run prefill, Save toggle.
9. On first sign-in, import the browser's existing history and saved queries, then clear them locally.

### Phase 3: safety foundation (required before anyone's own data)
10. Move blocking endpoints to plain `def`, so they run in the threadpool and one slow request can't block others.
11. Run every query in a `READ ONLY` transaction, with an 8 s statement timeout and a 1,000-row cap that is flagged in the UI.

### Phase 4: workspaces
12. Add a `workspaces` table: owner user, kind (demo / upload / connection), name, created_at, expiry. The demo workspace is shared and read-only.
13. Route each request to the active workspace's database. Make introspection schema-aware (it currently reads only `public`), and cache the schema per workspace.
14. History and saved queries record which workspace they belong to.

### Phase 5: file uploads
15. **Limits:** CSV or XLSX, ≤ 10 files, ≤ 10 MB total, ≤ 200k rows per file.
16. **Processing:**
    - infer column types (integer, numeric, date, timestamp, boolean, text);
    - sanitize identifiers;
    - detect foreign keys (`<table>_id` → that table's key).

    A **preview** step shows the user what was found before anything is imported.
17. **Import:** COPY into a private schema `ws_<id>` on Neon.
18. **Expiry:** after 7 days, with cleanup at startup and on a timer, and a storage quota per user (Neon free tier is 0.5 GB).
19. **No `.sql` dumps:** uploaded SQL could execute arbitrary statements.

### Phase 6: connect your own PostgreSQL
20. **SSRF guard:** resolve the host and refuse private, loopback, link-local and cloud-metadata addresses; re-check at connect time to defeat DNS rebinding.
21. **Connection test:** connect with a timeout and a test query, and show the SQL to create a read-only user (recommended).
22. **Storage:** credentials are encrypted with Fernet (`CREDENTIAL_KEY`) and deleted after 24 hours. They are never logged or returned to the browser.

### Phase 7: an AI that works on any schema
23. Make the extractor prompt schema-neutral: its examples are labelled as a sample schema, and the model must use only the provided tables.
24. Restrict demo-only business rules to the demo workspace: "top N = units sold", and "sales = completed orders".
25. Add a second, unrelated sample dataset (for example employees / departments / projects) with its own eval questions.

### Phase 8: frontend for workspaces
26. Add a **Connect** page (`/app/connect`) with two tabs:
    - **Upload:** drag and drop, schema preview, import;
    - **PostgreSQL:** URL, read-only user guide, test, connect.
27. Add a workspace switcher in the top bar. Schema, history and saved queries follow the active workspace. Expiry dates are visible.

### Phase 9: docs and live verification
28. Update the README, SETUP, Privacy page and CHANGELOG.
29. **Live checks:**
    - sign in with Google;
    - quota and anonymous tries;
    - upload, then query;
    - connect a read-only database, then query; writes are refused;
    - the demo eval stays 41/41, and the second dataset's eval passes.

## Verification (every phase)
- **Unit tests:**
  - token verification: bad audience, issuer or signature, expired tokens;
  - session expiry and revocation;
  - quota boundaries (20th allowed, 21st refused; the reset);
  - anonymous limits;
  - workspace isolation (user A can never read B's data or history);
  - type inference, FK detection;
  - SSRF cases;
  - encryption round trip;
  - read-only enforcement.
- **Browser checks** in headless Chrome, plus the live eval after each deploy. Only measured numbers are reported.
