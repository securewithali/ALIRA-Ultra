# 🟠 HunterCode

A lightweight CLI AI coding agent — inspired by Claude Code and OpenCode, built
in TypeScript + Node.js. Type `huntercode` in any terminal to launch an
interactive coding session scoped to the current directory.

HunterCode is **provider-agnostic**: the same agent loop and toolset work
across **Ollama**, **Anthropic**, **Gemini**, **OpenRouter**, and **NVIDIA**.
Switching backends is a config change, not a code change.

- **Lightweight** — one runtime dependency (`chalk`). Input via Node's built-in
  `readline`; HTTP via the built-in `fetch`. No heavy frameworks, no React.
- **Live streaming** — the model's text and reasoning stream **token-by-token**
  over real SSE for every cloud provider; each tool call shows a live action
  line and a collapsed result the moment it finishes — no silent "thinking" gaps.
- **Live diff approval** — edits show a colored diff **before** they're written;
  in manual mode you approve each one (`y` / `n` / `a` = yes-to-all), in auto
  mode they apply but still show the diff.
- **Visual task list** — for multi-step requests the agent lays out a todo panel
  and flips each task `○ → ◐ → ✔` as it works, one in-progress at a time.
- **Plan controls** — after `plan` mode produces a plan you get **Continue /
  Edit / Cancel**; the agent can also propose switching modes itself.
- **`@file` attach** — mention `@src/config.ts` in a message and its contents
  are loaded into context automatically (multiple mentions supported).
- **Context compaction** — long sessions auto-summarize older history near the
  model's context limit (or on demand via `/compact`) so they never overflow.
- **Sub-agents** — the main agent can dispatch focused sub-agents (sharing a
  bounded memory box) for isolated chunks of a big job (opt-in via config).
- **MCP support** — connect external [Model Context Protocol](https://modelcontextprotocol.io)
  servers; their tools merge into the agent's toolset.
- **Pluggable providers** — a single `Provider` interface normalizes the
  different tool-calling formats of each backend.
- **Three modes** — `agent` (full access), `plan` (read-only, proposes a plan),
  and `ask` (read-only Q&A).
- **Project memory** — durable `HUNTER.md` notes plus a per-project fix log,
  loaded into context every session (like Claude Code's `CLAUDE.md`).
- **Web aware** — `web_search` and `fetch_url` let it look things up and read
  docs/pages.
- **Orange everywhere** — warm Claude-inspired theme with live tool indicators
  and colored diffs.

## Requirements

- Node.js ≥ 18 (Node 22 recommended — native `fetch`).
- For the default backend: a running [Ollama](https://ollama.com) server with a
  tool-capable model such as `qwen2.5-coder`.

## Install

### From this repo (development)

```bash
git clone https://github.com/HunterisLive-1/HunterCode.git
cd HunterCode
npm install
npm run build
npm link          # makes `huntercode` available globally
```

Now run it from any project directory:

```bash
cd ~/my-project
huntercode
```

### Global install from a checkout

```bash
npm install -g .
```

To unlink the dev version later: `npm unlink -g huntercode`.

## How to use it

Launch `huntercode` inside the project you want to work on. You'll see the
orange banner and a prompt that shows the current mode:

```
hunter [agent] ›
```

Type a request in plain language and press Enter:

```
hunter [agent] › add a --version flag to src/cli.ts and update the README
```

The agent reads files, proposes edits with colored diffs, runs commands (asking
first before anything destructive), and gives a short summary when done. After a
non-trivial fix it saves a note to the project's memory (see below).

### Modes

Switch any time with `/mode <name>`. The current mode is shown in the prompt.

| Mode    | What it does                                                        |
| ------- | ------------------------------------------------------------------- |
| `agent` | Full access — reads, edits, writes, runs commands, saves memory.    |
| `plan`  | Read-only — investigates and proposes a step-by-step plan.          |
| `ask`   | Read-only — answers questions about your code, docs, or the web.    |

```
/mode plan      # explore safely and get a plan, no changes made
/mode ask       # ask "how does X work?" — read-only answers
/mode agent     # let it make the changes
```

In `plan` and `ask` modes the editing/command tools are disabled, so the agent
physically cannot modify your project.

### Slash commands

| Command                    | Description                                          |
| -------------------------- | ---------------------------------------------------- |
| `/help`                    | Show available commands                              |
| `/clear`                   | Reset the conversation history                       |
| `/mode [name]`             | Show or switch mode (`agent`, `plan`, `ask`)         |
| `/model [name]`            | Show, **list**, or switch the model                  |
| `/provider [name]`         | Show or switch the provider                          |
| `/apikey <provider> [key]` | Set a provider's API key from the terminal           |
| `/editapproval [auto\|manual]` | Apply edits automatically or after a `y/n/a` prompt |
| `/automode [auto\|manual]` | Let the agent switch modes itself, or ask first      |
| `/compact`                 | Summarize & shrink the conversation context          |
| `/init`                    | Scaffold a `HUNTER.md` for this project              |
| `/mcp`                     | List connected MCP servers and their tools           |
| `/exit`                    | Quit                                                 |

#### Command autocomplete

Type `/` and a live menu of commands appears right below the prompt, filtering as
you type — just like Claude Code / OpenCode. Use **↑/↓** to move through it.
**Enter** runs the highlighted command (e.g. `/he` + Enter runs `/help`); for a
command that takes an argument it expands first (`/mo` → `/mode `) and shows the
valid values. **Tab** completes without running. **Esc** closes the menu.

While the agent works you'll see a live indicator — **Thinking…** before it
replies, **Working…** between tool steps, and **Planning…** in plan mode.

### Live work: streaming, tool lines, and diff approval

The model's text and reasoning stream in **as they're generated** (real SSE for
Anthropic, Gemini, OpenRouter, NVIDIA; native streaming for Ollama). Each tool
call prints a live action line the moment it starts and a collapsed result when
it finishes:

```
→ Reading src/config.ts
  └ Read 128 lines
→ Editing src/agent.ts
  └ Edited (1 replacement)
```

Before any edit is written, HunterCode shows a colored diff. In **manual**
approval (the default) it asks `Apply this edit? [y] yes [n] no [a] yes-to-all`;
`a` stops re-prompting for the rest of the turn. In **auto** it applies
immediately but still shows the diff. Toggle with `/editapproval auto|manual`.

### Task lists

For a non-trivial, multi-step request the agent first lays out a plan as a live
task panel and works through it one item at a time:

```
Tasks
✔ Set up project structure
◐ Add Tailwind styling
○ Wire up routing
```

`○` pending · `◐` in-progress · `✔` done · `✗` failed. (Reliable on strong
models; weaker free models may skip it — it degrades gracefully.)

### Plan mode → Continue / Edit / Cancel

In `plan` mode, once a plan is produced you choose what happens next:

```
→ Plan ready. [c] Continue  [e] Edit  [x] Cancel
```

**Continue** switches to agent mode and executes the plan, **Edit** lets you
give feedback and regenerate it, **Cancel** stays idle. The agent can also
propose switching modes on its own — with `/automode manual` it asks first;
`/automode auto` lets it switch and just tells you.

### Attaching files with `@`

Mention a path with `@` and its contents are pulled into context (with line
numbers), no tool call needed:

```
hunter [agent] › what does @src/config.ts do, and is it used in @src/cli.ts?
```

Multiple mentions all load; a path that doesn't exist gives a clean warning.

### Long sessions: context compaction

HunterCode tracks the conversation size and, near the model's context window,
automatically summarizes older history into a compact note — preserving goals,
decisions, file paths, and open tasks — so long sessions never overflow. You'll
see `↺ Compacted context (saved ~N tokens)`. Force it any time with `/compact`.

### Sub-agents (advanced, opt-in)

The main agent can break a big job into chunks and dispatch **sub-agents** for
isolated pieces, each with only the context it needs and a shared, size-bounded
memory box so findings flow between them. Disabled by default (powerful on
strong models, flaky on weak ones); enable in config:

```json
"subagents": { "enabled": true, "maxPerTurn": 3 }
```

### MCP servers

Connect external [Model Context Protocol](https://modelcontextprotocol.io)
servers and their tools become available to the agent. Add them to config under
`mcpServers` (stdio transport):

```json
"mcpServers": {
  "filesystem": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
  }
}
```

On startup HunterCode connects each enabled server, discovers its tools (exposed
as `mcp_<server>_<tool>`), and merges them in. Run `/mcp` to list connected
servers and tools. A server that fails to connect warns and is skipped — it
never crashes the session.

### Choosing a model

- **Switch directly:** `/model qwen2.5-coder:7b`
- **Pick from a list:** run `/model` with no argument. For Ollama it lists the
  models you actually have installed (queried live from the server) — pick any
  by number or name; works with 3B/4B/7B or heavier models. For cloud providers
  it shows curated suggestions (free-tier options are flagged).

```
hunter [agent] › /model
Available models for ollama:
  1. qwen2.5-coder:7b
  2. llama3.1:8b
  3. deepseek-coder-v2:latest
Select (number or name, blank to cancel): 1
```

### Using a cloud provider (Anthropic / Gemini / OpenRouter)

Ollama needs no key. For a cloud provider, set its key from the terminal and
switch — switching also picks a sensible default model for that provider:

```
/apikey gemini AIza...your-key...
/provider gemini
# Gemini defaults to a free model (gemini-2.5-flash). Change it any time:
/model gemini-2.5-pro
```

Google models: the flash family (`gemini-2.5-flash`, `gemini-2.0-flash`,
`gemini-1.5-flash`) has a generous **free tier** and is the default; paid models
like `gemini-2.5-pro` are selectable too. OpenRouter also exposes free models
such as `google/gemini-2.0-flash-exp:free`.

### NVIDIA (free models + thinking)

NVIDIA's build platform exposes an OpenAI-compatible API with a usable **free
tier**. Grab a `nvapi-...` key from [build.nvidia.com](https://build.nvidia.com),
then:

```
/apikey nvidia nvapi-...your-key...
/provider nvidia
# Defaults to meta/llama-3.3-70b-instruct (solid tool calling). Switch any time:
/model nvidia/llama-3.3-nemotron-super-49b-v1.5
```

Curated free NVIDIA models: `meta/llama-3.3-70b-instruct`,
`qwen/qwen3-next-80b-a3b-instruct`,
`nvidia/llama-3.3-nemotron-super-49b-v1.5`, `openai/gpt-oss-120b`,
`mistralai/codestral-22b-instruct-v0.1`.

**Thinking display:** the nemotron-super and gpt-oss models expose a reasoning
trace. When a model returns one, HunterCode shows it in a dimmed **💭 Thinking**
block above the answer — so you can see how the model reasoned before it
responded.

Keys can also be edited directly in the config file (below); `/apikey` just does
it for you without leaving the CLI.

## Automation: `run` and `serve`

Beyond the interactive REPL, HunterCode has two non-interactive entrypoints for
scripts and other tools (e.g. driving it from another app):

- **`huntercode run [task] --dir <path> --file <promptFile> --summary-file <path> --progress-file <path>`**
  — executes one task to completion, streaming the model's thinking, tool calls,
  and edits to stdout (great inside a VS Code terminal for "watch it work"), then
  writes the final summary to `--summary-file` and exits 0/1.
- **`huntercode serve --port 4096 --dir <path>`** — a small HTTP API
  (`/global/health`, `/path`, `/session`, `/session/:id/message`,
  `/session/:id/diff`, `/session/:id/progress`) for a session-based, headless
  workflow.

### Progress channel (for live UIs / orchestrators)

Both entrypoints expose the same structured progress events so a caller can show
live progress instead of waiting for the final summary:

- **`run --progress-file <path>`** appends one JSON object per line (JSONL) as the
  agent works — `started`, `tool`, `tool_result`, `todos`, `notice`, then `done`
  (or `error`). Tail the file to drive a UI:
  ```json
  {"t":1718…, "type":"tool", "label":"Writing note.txt"}
  {"t":1718…, "type":"tool_result", "summary":"Created note.txt (1 lines).", "ok":true}
  {"t":1718…, "type":"done", "summary":"…final summary…"}
  ```
- **`serve`** buffers the same events per session. Poll
  `GET /session/:id/progress?since=<n>` during an in-flight message — it returns
  `{ "events": [...], "next": <count> }`; pass the previous `next` as `since` to
  get only new events. The message response also includes
  `info.changedFiles`.

Both read config from `~/.huntercode/config.json` and accept env overrides
(`HUNTERCODE_PROVIDER`, `HUNTERCODE_MODEL`, `NVIDIA_API_KEY`, …) plus a local
`.env`, so a caller can select a free NVIDIA model without writing any config.

## Running commands & dev servers

In `agent` mode HunterCode can run shell commands for you — install dependencies,
build, run tests, execute scripts — and it reads the output (stdout, stderr, exit
code) to fix failures and re-run on its own, like Claude Code / OpenCode.

For **long-running processes** that never exit on their own — dev servers and
watchers such as `npm run dev`, `vite`, or `flask run` — it starts them in the
**background** so it can keep working, then reads their logs and stops them when
done:

- `run_bash` with `background: true` — start a process and keep it running.
- `check_logs` — read what a background process has printed so far.
- `stop_process` — stop it.

Background processes are stopped automatically when you exit HunterCode. Foreground
commands stream their output live and time out after 2 minutes (a hint suggests
running them in the background instead).

## Project memory

HunterCode loads two project files into context on every session:

- **`HUNTER.md`** (project root) — durable instructions and conventions, like
  Claude Code's `CLAUDE.md`. Run `/init` to scaffold one by scanning the project
  (package manager, languages, scripts, layout), or let the agent append notes
  to it via the `remember` tool (it asks first). Commit it so the team shares it.
- **`.huntercode/memory.md`** — a dated fix log. When the agent finishes a
  meaningful change in `agent` mode it appends **what the problem was and how it
  was fixed** via `save_memory`.

Both are plain Markdown — read, edit, or commit them. On the next session in that
project, their contents are loaded automatically so HunterCode remembers your
conventions and the history of fixes.

## Web search & reading docs

Available in every mode (they're read-only):

- `web_search` — searches the web (via DuckDuckGo, no API key needed) and returns
  the top results.
- `fetch_url` — fetches a page or document and returns its readable text.

Just ask naturally, e.g. `ask how do I configure X in the latest version of
<library>?` and the agent will search and read the relevant docs.

> Network access depends on your environment. If a request is blocked, the tool
> returns a clear error rather than failing the session.

## Configuration

Config lives at `~/.huntercode/config.json` and is created with defaults on first
run:

```json
{
  "provider": "ollama",
  "model": "qwen2.5-coder",
  "ollamaUrl": "http://localhost:11434",
  "apiKeys": {
    "anthropic": "",
    "gemini": "",
    "openrouter": "",
    "nvidia": ""
  },
  "temperature": 0.7,
  "mode": "agent",
  "editApproval": "manual",
  "autoMode": "manual",
  "compactThreshold": 0.75,
  "subagents": { "enabled": false, "maxPerTurn": 3 },
  "mcpServers": {}
}
```

- `editApproval` — `manual` shows a diff and asks before each edit; `auto`
  applies and shows the diff. Also toggled with `/editapproval`.
- `autoMode` — `manual` makes the agent ask before switching modes; `auto` lets
  it switch and just informs you. Also toggled with `/automode`.
- `compactThreshold` — fraction of the model's context window at which older
  history is auto-summarized (0–1).
- `subagents` — opt-in sub-agent dispatch and the per-turn cap.
- `mcpServers` — external MCP servers to connect on startup (see above).

## Tools

| Tool          | What it does                                                              |
| ------------- | ------------------------------------------------------------------------ |
| `read_file`   | Read a file with line numbers (reference only), with `offset`/`limit`.   |
| `str_replace` | Exact-match edit: replaces a unique `old_string`. No line-number edits.  |
| `write_file`  | Create or overwrite a file (creates parent dirs), with a diff.           |
| `list_files`  | List a directory tree, ignoring `node_modules`, `.git`, `dist`, etc.     |
| `grep`        | Recursive regex search across files.                                     |
| `run_bash`    | Run a shell command (live output); `background: true` for dev servers.   |
| `check_logs`  | Read output from a background process (or list running ones).            |
| `stop_process`| Stop a background process started by `run_bash`.                         |
| `web_search`  | Search the web (DuckDuckGo, keyless) for docs/answers.                   |
| `fetch_url`   | Fetch a URL and return readable text.                                    |
| `save_memory` | Append a fix summary to `.huntercode/memory.md` (agent mode).            |
| `remember`    | Save a durable note/convention to `HUNTER.md` (asks first).              |
| `update_todos`| Create/update the live task panel for multi-step work.                  |
| `set_mode`    | Switch the agent's own mode (`agent`/`plan`/`ask`) when the task fits.   |
| `spawn_subagent` | Dispatch a focused sub-agent for an isolated sub-task (opt-in).       |

## Project structure

```
src/
  cli.ts            entry: banner, config, REPL, slash commands, plan controls
  agent.ts          the agentic loop + conversation state + modes/memory
  modes.ts          agent/plan/ask mode definitions and tool gating
  memory.ts         project memory (HUNTER.md + .huntercode/memory.md)
  init.ts           /init — scaffold a starter HUNTER.md
  config.ts         ~/.huntercode/config.json load/save + env overrides
  types.ts          normalized Message / ToolSchema / Provider types
  agent/
    compaction.ts   context-window tracking + summarization
    subagent.ts     focused sub-agent mini-loop
    sharedMemory.ts bounded shared memory box for sub-agents
  context/
    attachments.ts  @file mention parsing
  tools/            one file per tool + registry
  providers/        Provider impls (ollama, anthropic, gemini, openrouter, nvidia)
                    + sse.ts (shared SSE/streaming plumbing)
  mcp/              minimal stdio JSON-RPC MCP client + tool merge
  ui/               renderer (all output), theme (orange), banner, diff, prompt
```

### Adding a provider

Implement the `Provider` interface from `src/types.ts` — three conversions:
tool **definitions**, tool **call** parsing, and tool **result** formatting,
plus `chat` and a `chatStream` that emits text/reasoning deltas (the shared
`providers/sse.ts` helper covers SSE framing) — then register it in
`src/providers/index.ts`. The agent loop is untouched. If a backend can't
stream, `chatStream` can fall back to a buffered `chat` call.

## Contributors

- **HunterisLive-1** — <alimd904@gmail.com>

Contributions welcome — open an issue or PR.

## License

MIT
