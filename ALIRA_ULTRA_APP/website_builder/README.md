# website_builder

This package contains the ALIRA WebForge website builder module.

## Structure

- `config.py` — loads `.env` keys and project path settings
- `webforge_manager.py` — main controller for plan → generate → deploy
- `main.py` — simple CLI runner
- `webforge_integration.py` — integration helper for ALIRA GUI

### Subpackages

- `agents/`
  - `planner_agent.py` — detects website commands and creates plans
  - `content_agent.py` — generates website text content
  - `generator_agent.py` — generates HTML/CSS/JS output

- `project/`
  - `project_manager.py` — saves files to local project folders

- `preview/`
  - `preview_server.py` — starts a local HTTP preview server

- `deploy/`
  - `github_service.py` — pushes project files to GitHub
  - `vercel_service.py` — deploys to Vercel
  - `qr_display.py` — shows QR code popups for live URLs

- `database/`
  - `projects_db.py` — JSON-backed project metadata storage

## Setup

1. Copy `website_builder/.env.example` to `website_builder/.env`
2. Fill in the required keys
3. Install dependencies:

```bash
pip install python-dotenv requests google-genai qrcode[pil]
```

## Run

```bash
python -m website_builder.main "create a dark gaming website"
```
