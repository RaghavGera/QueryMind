# Contributing to QueryMind

Thank you for considering a contribution. QueryMind turns plain-English questions into safe, parameterized SQL, and it asks for clarification instead of guessing. This guide explains how the project is built and what a good change looks like.

## Principles

Every contribution is held to these principles. They are the reason the project exists.

1. **SQL is generated, never free-written.** The language model produces a structured intent; the deterministic generator in `app/sql_generator.py` produces the SQL. Never execute SQL text that came from a model.
2. **Ambiguity is a feature.** If a question can reasonably mean two things, the right response is a clarification question, not a guess.
3. **Safety is enforced in code.**
   - Identifiers are checked against the live schema.
   - Values are always passed as parameters.
   - Writes require explicit confirmation.
   - DELETE is refused.
4. **Claims are measured.** Any statement about accuracy, latency or cost, in code, docs or the UI, must come from a real measurement. Note where and when it was taken.

## Development setup

Prerequisites:
- Python 3.10+
- PostgreSQL
- Node.js 20.19+ or 22.12+
- Git
- An API key for Gemini and/or Groq

```bash
git clone https://github.com/<your-username>/Text-to-SQL.git
cd Text-to-SQL

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                 # set DB_* and GEMINI_API_KEY and/or GROQ_API_KEY
createdb text_to_sql
psql -d text_to_sql -f database/text_to_sql_database.sql

uvicorn app.main:app --reload        # API on http://127.0.0.1:8000

cd frontend
# create frontend/.env.local containing: VITE_API_BASE_URL=http://127.0.0.1:8000
npm install
npm run dev                          # web app on http://localhost:5173
```

See [SETUP.md](SETUP.md) for every environment variable and for troubleshooting.

## Making a change

### Backend

- Follow PEP 8, use type hints, and write docstrings that explain *why* as well as *what*.
- **New query capabilities touch the whole pipeline.** Each needs:
  - a field in the Pydantic models (`app/models.py`);
  - guidance in the extractor prompt (`app/intent_extractor.py`);
  - normalization in the converter (`app/intent_converter.py`);
  - rendering in the generator (`app/sql_generator.py`);
  - tests.
- **All LLM calls go through the provider chain** in `app/openai_client.py`. Keep `max_tokens` at 800 unless you have re-measured against the providers' rate limits.

### Frontend

- **Styling:** use the existing design tokens (`frontend/tailwind.config.js`, `frontend/src/styles/globals.css`) and components rather than one-off styles.
- **Motion helpers** live in `frontend/src/motion/`.
- **Scroll-linked scenes** must go through `PinnedChapter`, which drives animations from a plain motion value on purpose (see the comment in that file).
- **Every animation needs a reduced-motion path.**
- **The WebGL scene is decorative.** All content must stay in the DOM.
- **Copy on the public pages describes only what the product does today.** Numbers and SQL shown there must be real captures.

## Testing

All changes need tests, and the existing suites must stay green.

```bash
pytest testing/                      # backend; database tests skip without PostgreSQL
cd frontend && npm test              # frontend unit tests
cd frontend && npm run build         # the production build must succeed
```

- **Tests that call a real language model are opt-in**, because they spend tokens: `python -m testing.run_tests --live`.
- **Changes that affect answers should be checked with the evaluation harness.** It runs the 41 questions in `testing/eval_questions.json` and checks the generated SQL, the rows and clarification behaviour:

```bash
python -m testing.eval_harness --offline                         # in-process, no database
python -m testing.eval_harness --base-url http://127.0.0.1:8000  # your local API
```

When you fix a bug, add a test that fails without the fix.

## Commits and pull requests

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <summary>

<what changed and why>
```

Common types:
- `feat`: a new feature
- `fix`: a bug fix
- `docs`: documentation
- `refactor`: a code change that neither fixes a bug nor adds a feature
- `test`: tests
- `chore`: maintenance

For example:

```
fix(sql): join the FK holder when the referenced table is already joined

PostgreSQL raised "table name specified more than once" for questions that
touched orders and customers twice. Adds a regression test.
```

Before opening a pull request:

- [ ] Tests pass locally (`pytest testing/`, `npm test`, `npm run build`)
- [ ] New behaviour has tests, and bug fixes have a regression test
- [ ] User-visible changes have an entry in [CHANGELOG.md](CHANGELOG.md)
- [ ] Documentation is updated (README, SETUP, or code comments)
- [ ] Any accuracy or performance claim cites a measurement
- [ ] No secrets, `.env` files or local artifacts are committed

In the pull request description, explain what changed, why, and how you verified it. Include screenshots for UI changes.

## Reporting bugs

Open a GitHub issue that includes:

- **What you asked and what you expected**: the question, and the expected SQL or result.
- **What happened instead**: the response status, the generated SQL and any error message.
- **How to reproduce it**: the steps, and whether it happens locally, on the live app, or both.
- **Your environment**: OS, Python and Node versions, and the AI provider and model if known (the API logs `provider=` and `model=` for every call).

Known limitations are tracked, with evidence, in [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md). Please check there first.

## Suggesting features

Feature requests are welcome as GitHub issues. Describe the question you want to be able to ask, the answer you expect, and why the current behaviour falls short. The roadmap in the [README](README.md#roadmap) lists what is planned next.

## License

By contributing, you agree that your contributions are licensed under the project's [MIT License](LICENSE).
