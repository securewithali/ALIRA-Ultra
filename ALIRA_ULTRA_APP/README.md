# ALIRA ULTRA v8.0 — AI Voice Assistant + ALIRA Coder

```
  ⬡ ALIRA ULTRA  |  AI Voice Assistant  +  ALIRA Coder AI Website Builder
  Voice se bolo → ALIRA sunti hai → Website ban jaati hai → Live deploy!
```

## Quick Start

### Step 1: Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: ALIRA Coder Setup
```bash
# Install Node.js 18+ first: https://nodejs.org
python setup_ALIRA_coder.py
```

### Step 3: Run ALIRA
```bash
python TABBU.py
```

### Step 4: Website banao!
ALIRA se bolo:
- "gaming website banao dark theme ke saath"
- "portfolio website bana mere liye"
- "restaurant ka website create karo"

**ALIRA Coder panel automatically khulega!**

---

## Architecture

```
ALIRA ULTRA v8.0
├── TABBU.py                      # Main ALIRA window (PyQt5)
├── ALIRA_coder_integration.py    # ALIRA Coder Python bridge
├── ALIRA_coder/                  # Node.js AI coding engine (renamed HunterCode)
│   ├── src/agent.ts             # Core AI agent
│   ├── src/run.ts               # Headless runner
│   ├── src/providers/gemini.ts  # Gemini provider
│   └── dist/                    # Compiled JS (after build)
├── website_builder/             # WebForge (existing python builder)
├── Projects/                    # Generated websites save hote hain
└── setup_ALIRA_coder.py          # One-click setup
```

## How It Works

```
User Voice Command
      ↓
ALIRA Voice Recognition (Gemini WebSocket)
      ↓
_is_website_command() check
      ↓
ALIRACoderOverlay.show_panel(task)  ← ALIRA UI pe panel aata hai
      ↓
node dist/run.js --progress-file tmp.jsonl
      ↓
AI agent → tools → files create hote hain
      ↓ (live streaming via JSON progress file)
Qt signals → live UI update
      ↓
Done → ALIRA bolti hai congratulations!
```

## Configuration

`.env` file:
```
GEMINI_API_KEY=your_key
GITHUB_TOKEN=ghp_...    (for WebForge deploy)
VERCEL_TOKEN=vcp_...    (for WebForge deploy)
```

## EXE Build

```bash
python setup_ALIRA_coder.py  # build Node.js first
pyinstaller ALIRA_ULTRA.spec
```

Note: Target PC pe Node.js 18+ install hona chahiye EXE ke liye.

## Troubleshooting

- **"ALIRA Coder build nahi mili"**: `cd ALIRA_coder && npm install && npm run build`
- **"Node.js nahi mila"**: https://nodejs.org install karo
- **"API key error"**: `.env` mein `GEMINI_API_KEY` add karo

---
ALIRA ULTRA v8.0 | ALIRA Coder powered by HunterCode engine (MIT License)
