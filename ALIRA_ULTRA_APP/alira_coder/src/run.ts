/**
 * `ALIRA-coder run` — non-interactive, single-task execution.
 *
 * Designed for headless / automated callers (e.g. Maya) and for running inside a
 * VS Code integrated terminal so a human can watch the work live ("vibe coding"):
 * it streams the model's thinking, tool calls, and answer to stdout, runs one
 * task to completion (auto-approving tool actions), optionally writes the final
 * summary to a file, and exits 0 on success / non-zero on error.
 *
 * Usage:
 *   ALIRA-coder run [task] --dir <path> --file <promptFile> \
 *     --provider <p> --model <m> --summary-file <path>
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { loadConfig, loadDotEnv, applyEnvOverrides, type Config } from "./config.js";
import { getProvider, PROVIDER_NAMES, DEFAULT_MODELS } from "./providers/index.js";
import { Session, type AgentUI } from "./agent.js";
import { theme } from "./ui/theme.js";
import { createRenderer } from "./ui/renderer.js";
import { parseAttachments } from "./context/attachments.js";
import { fileProgressSink, withProgress, nullProgressSink } from "./progress.js";
import { killAll } from "./tools/processes.js";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Load .env file from the given directory or parent directories.
 * Sets process.env for each KEY=VALUE line found.
 */
function loadEnvFile(dir: string): void {
  const envPath = join(dir, ".env");
  if (!existsSync(envPath)) return;
  try {
    const lines = readFileSync(envPath, "utf8").split("\n");
    for (const raw of lines) {
      const line = raw.trim();
      if (!line || line.startsWith("#")) continue;
      const eqIdx = line.indexOf("=");
      if (eqIdx < 1) continue;
      const key = line.slice(0, eqIdx).trim();
      const val = line.slice(eqIdx + 1).trim();
      if (key && !process.env[key]) {
        process.env[key] = val;
      }
    }
  } catch {
    // Best-effort
  }
}

interface RunArgs {
  task: string;
  dir: string;
  summaryFile?: string;
  progressFile?: string;
  provider?: string;
  model?: string;
}

function parseArgs(argv: string[]): RunArgs {
  const out: RunArgs = { task: "", dir: process.cwd() };
  const positional: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i] ?? "";
    switch (a) {
      case "--dir": out.dir = next(); break;
      case "--file": {
        const f = next();
        try {
          out.task = readFileSync(f, "utf8").trim();
        } catch (e) {
          console.error(theme.error(`Could not read --file ${f}: ${(e as Error).message}`));
          process.exit(2);
        }
        break;
      }
      case "--summary-file": out.summaryFile = next(); break;
      case "--progress-file": out.progressFile = next(); break;
      case "--provider": out.provider = next(); break;
      case "--model": out.model = next(); break;
      default:
        if (a.startsWith("--")) { next(); /* skip unknown flag value */ }
        else positional.push(a);
    }
  }
  // A positional task wins only if --file didn't already supply one.
  if (!out.task && positional.length) out.task = positional.join(" ");
  return out;
}

export async function runMain(argv: string[]): Promise<void> {
  const args = parseArgs(argv);
  if (!args.task) {
    console.error(theme.error('ALIRA-coder run: no task. Pass text or --file <path>.'));
    process.exit(2);
  }

  // Load .env from ALIRA_coder dir and task dir
  const __mcDir = dirname(fileURLToPath(import.meta.url));
  loadEnvFile(join(__mcDir, "..")); // ALIRA_coder root
  loadEnvFile(args.dir); // task dir

  // Map GEMINI_API_KEY to config if set
  if (process.env.GEMINI_API_KEY) {
    process.env.GEMINI_API_KEY = process.env.GEMINI_API_KEY;
  }

  loadDotEnv(args.dir);
  let config: Config = applyEnvOverrides(loadConfig());
  // A --provider flag only applies when it names a known provider; otherwise we
  // keep the global config (and ignore a --model that came with it).
  if (args.provider && PROVIDER_NAMES.includes(args.provider as Config["provider"])) {
    const switched = config.provider !== (args.provider as Config["provider"]);
    config = { ...config, provider: args.provider as Config["provider"] };
    if (args.model) config = { ...config, model: args.model };
    // Provider badla par model nahi diya => us provider ka default model (warna
    // global config ka "qwen2.5-coder" Gemini ko bheja jata tha => 404).
    else if (switched) config = { ...config, model: DEFAULT_MODELS[args.provider as Config["provider"]] };
  } else if (args.model && !args.provider) {
    config = { ...config, model: args.model };
  } else if (args.provider) {
    console.error(theme.dim(`Ignoring unknown --provider "${args.provider}"; using global config (${config.provider}).`));
  }

  const provider = getProvider(config);

  // Headless UI: stream everything to stdout, auto-approve tool actions.
  const r = createRenderer(process.stdout);
  const ui: AgentUI = {
    onText: (delta) => r.text(delta),
    onReasoning: (delta) => r.reasoning(delta),
    onToolCall: (label) => r.toolStart(label),
    onToolResult: (summary, ok) => r.toolEnd(summary, ok),
    print: (line) => r.print(line),
    onDiff: (diff) => r.diff(diff),
    onTodos: (todos) => r.todos(todos),
    notice: (line) => r.notice(line),
    confirm: async () => true, // headless: auto-approve everything
    setStatus: (label) => r.status(label),
  };

  // Optional progress channel: append a JSON line per event for a caller (e.g.
  // Maya) to tail and surface live progress.
  const progress = args.progressFile ? fileProgressSink(args.progressFile) : nullProgressSink;
  const liveUI = args.progressFile ? withProgress(ui, progress) : ui;

  console.log(
    theme.dim(`ALIRA-coder run · ${config.provider} · ${config.model} · ${args.dir}`),
  );

  const session = new Session(provider, config, args.dir);
  progress.emit("started", { provider: config.provider, model: config.model, dir: args.dir });
  try {
    // Resolve any @file mentions in the task into context blocks.
    const { text, warnings } = parseAttachments(args.task, args.dir);
    for (const warn of warnings) r.notice(warn);
    const summary = await session.runTurn(text, liveUI);
    process.stdout.write("\n");
    if (args.summaryFile) {
      writeFileSync(args.summaryFile, (summary || "Task complete.").trim() + "\n", "utf8");
    }
    progress.emit("done", { summary: (summary || "Task complete.").trim() });
    finish(0);
  } catch (e) {
    const msg = (e as Error).message;
    process.stdout.write("\n");
    console.error(theme.error(`Error: ${msg}`));
    if (args.summaryFile) {
      try { writeFileSync(args.summaryFile, `ERROR: ${msg}\n`, "utf8"); } catch { /* ignore */ }
    }
    progress.emit("error", { message: msg });
    finish(1);
  }
}

/**
 * Clean shutdown. Kills any background processes a tool started, sets the exit
 * code, and lets the event loop drain naturally — calling `process.exit()`
 * synchronously while stdout writes are in flight triggers a libuv assertion on
 * Windows (UV_HANDLE_CLOSING). A long unref'd fallback force-exits only if some
 * handle unexpectedly lingers, so an automated caller is never left hanging.
 */
function finish(code: number): void {
  killAll();
  process.exitCode = code;
  setTimeout(() => process.exit(code), 3000).unref();
}
