# Repository Guidelines

## Project Structure & Module Organization
ALIRA ULTRA is a PyQt5 desktop voice assistant (`tabbu.py` is the main window/entry point, `Main_normal.py` and `tabbu_startup.py` handle boot flow) that embeds an AI website-builder pipeline. Voice commands are matched by `_is_website_command()` and routed to **one of two independent builders**:
- `website_builder/` — Python "WebForge" pipeline (`agents/` plan → content → generate, `deploy/` pushes to GitHub/Vercel, `project/` and `database/` persist output to `Projects/`).
- `alira_coder/` — a separate Node.js/TypeScript AI coding agent (fork of "HunterCode", provider-agnostic across Ollama/Anthropic/Gemini/OpenRouter/NVIDIA). `alira_coder_integration.py` bridges it into the Qt UI by spawning `node dist/run.js --progress-file tmp.jsonl` and streaming JSON progress lines back into Qt signals.

`TABBU_modules/` holds feature modules (face auth, licensing/`license_client.py`, cloud database, activation) used by the main app; `admin_and_build_tools/` contains developer-only tooling (keygen, EXE build, PyPI publish) and is excluded from the packaged distribution. `ALIRA/` is the pip-installable CLI shim (`ALIRA`, `ALIRA-reset`, `ALIRA-upgrade` — see `ALIRA/cli.py`) that gates app launch behind license activation before importing `Main_normal`. `backend/` is a standalone FastAPI licensing server (Firebase Admin SDK) meant to run only on the server side — never bundled with the client.

## Build, Test, and Development Commands
```bash
pip install -r requirements.txt        # Python deps (client)
python setup_alira_coder.py             # npm install + tsc build for ALIRA_coder/, writes ~/.ALIRA-coder/config.json
python tabbu.py                         # run ALIRA (main entry point)
ALIRA / alira-reset / ALIRA-upgrade       # run via installed CLI (ALIRA/cli.py) with license activation
pyinstaller ALIRA_ULTRA.spec            # build Windows EXE (run setup_ALIRA_coder.py first)
```
Inside `alira_coder/`:
```bash
npm install && npm run build   # tsc compile to dist/
npm run dev                    # tsc -w
npm start                      # node dist/cli.js
```
Backend (`backend/`): `pip install -r backend/requirements.txt` then run with `uvicorn main:app`; requires Firebase Admin credentials, never ship this to clients.

## Coding Style & Naming Conventions
No linter/formatter config is present in this repo — match the surrounding file's style. Python modules mix English identifiers with Hinglish comments/strings (e.g. `_ensure_activation`, log lines like `"License cleared."`); preserve this convention rather than translating existing strings. `alira_coder/tsconfig.json` enables `strict: true` — keep new TypeScript strict-mode clean (`noUnusedLocals`/`noUnusedParameters` are explicitly disabled, so unused vars are tolerated there). Client-facing Python packages (`alira`, `tabbu_modules`, `website_builder`) must never import `firebase-admin` or `google-cloud-firestore` — those are backend-only (see the comment block in `pyproject.toml`); `pyrebase4` is the client-safe Firebase SDK.

## Testing Guidelines
No automated test suite or test runner is configured in this repository. Validate changes by running the affected entry point directly (`python tabbu.py` for the assistant, `npm run build` in `alira_coder/` for the TS agent, `python -m website_builder.main "<prompt>"` for WebForge).

## Commit & Pull Request Guidelines
This working copy has no git history to derive conventions from. Write clear, present-tense commit messages describing the change; keep client and backend (`backend/`) changes in separate commits where possible since they ship independently.
