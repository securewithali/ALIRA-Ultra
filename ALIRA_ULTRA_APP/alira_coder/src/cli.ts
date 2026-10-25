#!/usr/bin/env node
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { loadConfig, saveConfig, type Config, type ProviderName } from "./config.js";
import {
  getProvider,
  PROVIDER_NAMES,
  DEFAULT_MODELS,
  MODEL_PRESETS,
} from "./providers/index.js";
import { Session, type AgentUI } from "./agent.js";
import { MODES, type Mode } from "./modes.js";
import { banner } from "./ui/banner.js";
import { theme } from "./ui/theme.js";
import { createRenderer } from "./ui/renderer.js";
import { createPrompt } from "./ui/prompt.js";
import { computeSuggestions } from "./commands.js";
import { parseAttachments } from "./context/attachments.js";
import { scaffoldALIRACoderMd } from "./init.js";
import { ALIRACoderPath } from "./memory.js";
import { connectMcpServers, mcpStatus, closeMcpServers } from "./mcp/index.js";
import { killAll } from "./tools/processes.js";

function getVersion(): string {
  try {
    const here = dirname(fileURLToPath(import.meta.url));
    const pkg = JSON.parse(readFileSync(join(here, "..", "package.json"), "utf8"));
    return pkg.version ?? "0.2.0";
  } catch {
    return "0.2.0";
  }
}

const HELP = `
${theme.bold("Commands")}
  ${theme.primary("/help")}                Show this help
  ${theme.primary("/clear")}               Reset the conversation history
  ${theme.primary("/mode")} [name]         Show or switch mode (${MODES.join(", ")})
  ${theme.primary("/model")} [name]        Show, list, or switch the model
  ${theme.primary("/provider")} [name]     Show or switch the provider (${PROVIDER_NAMES.join(", ")})
  ${theme.primary("/apikey")} <p> [key]    Set the API key for a provider
  ${theme.primary("/editapproval")} [a|m]  Apply edits automatically or after a y/n/a prompt
  ${theme.primary("/automode")} [a|m]      Let the agent switch modes by itself, or ask first
  ${theme.primary("/compact")}             Summarize & shrink the conversation context
  ${theme.primary("/init")}                Scaffold a ALIRA_CODER.md for this project
  ${theme.primary("/mcp")}                 List connected MCP servers and their tools
  ${theme.primary("/exit")}                Quit ALIRA Coder

${theme.bold("Modes")}
  ${theme.primary("agent")}  Full access: reads, edits, writes, runs commands, saves memory.
  ${theme.primary("plan")}   Read-only: investigates and proposes a step-by-step plan.
  ${theme.primary("ask")}    Read-only: answers questions about code, docs, or the web.

${theme.bold("Tips")}
  ${theme.dim("Mention")} ${theme.primary("@path/to/file")} ${theme.dim("in a message to attach its contents.")}
  ${theme.dim("In plan mode, after a plan you can Continue / Edit / Cancel.")}

Type anything else to talk to the agent.
`;

function modeColor(mode: Mode): string {
  return theme.accent(`[${mode}]`);
}

async function main() {
  const cwd = process.cwd();
  let config = loadConfig();
  let provider = getProvider(config);
  const session = new Session(provider, config, cwd);

  const prompt = createPrompt({
    completions: (line) => computeSuggestions(line, { provider: config.provider }),
  });

  const ask = (q: string): Promise<string> => prompt.question(q);

  // All terminal output flows through the renderer (spinner, streaming text,
  // tool action lines, diffs, todo panel). Interactive prompts stay here in the
  // CLI, which owns stdin.
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
    confirm: async (question) => {
      r.flushLine();
      const answer = await ask(theme.accent("? ") + question + theme.dim(" [y/N] "));
      return /^y(es)?$/i.test(answer.trim());
    },
    approveEdit: async (path, diff) => {
      r.diff(diff);
      const answer = (
        await ask(theme.accent("? ") + `Apply this edit to ${path}? ` + theme.dim("[y] yes  [n] no  [a] yes-to-all "))
      ).trim().toLowerCase();
      if (answer === "a" || answer === "all") return "all";
      if (answer === "n" || answer === "no") return "no";
      return "yes";
    },
    setStatus: (label) => r.status(label),
  };

  const promptStr = () =>
    theme.bold("hunter") + " " + modeColor(session.getMode()) + theme.accent(" › ");

  const statusLine = () =>
    "  " +
    theme.primary(config.provider) +
    theme.dim(" · ") +
    theme.primary(config.model) +
    theme.dim(" · ") +
    theme.primary(session.getMode()) +
    theme.dim(" · v" + getVersion()) +
    "\n";

  if (process.stdout.isTTY) console.clear();
  console.log(banner(getVersion()));
  console.log(statusLine());

  const rebuildProvider = () => {
    provider = getProvider(config);
    session.setProvider(provider, config);
  };

  const chooseModel = async (): Promise<void> => {
    // Prefer a live list for Ollama; fall back to curated presets.
    let options: string[] = [];
    if (config.provider === "ollama" && provider.listModels) {
      try {
        options = await provider.listModels();
      } catch {
        options = [];
      }
    }
    if (!options.length) {
      options = MODEL_PRESETS[config.provider].map(
        (p) => p.value + (p.free ? "  (free tier)" : ""),
      );
    }

    console.log(theme.dim(`Available models for ${config.provider}:`));
    options.forEach((o, i) => console.log(theme.primary(`  ${i + 1}. `) + o));
    const sel = (await ask(theme.accent("Select (number or name, blank to cancel): "))).trim();
    if (!sel) return;

    let chosen = sel;
    const asNum = Number(sel);
    if (Number.isInteger(asNum) && asNum >= 1 && asNum <= options.length) {
      // Strip any "(free tier)" annotation from preset labels.
      chosen = options[asNum - 1].split("  (")[0].trim();
    }
    config = { ...config, model: chosen };
    saveConfig(config);
    rebuildProvider();
    console.log(theme.dim("Model set to ") + theme.primary(config.model));
  };

  // Returns true when the session should exit.
  const handleCommand = async (input: string): Promise<boolean> => {
    const [cmd, ...rest] = input.trim().slice(1).split(/\s+/);
    const arg = rest.join(" ").trim();

    switch (cmd) {
      case "help":
        console.log(HELP);
        return false;

      case "clear":
        session.clear();
        // Wipe the scrollback and redraw the fresh start screen.
        if (process.stdout.isTTY) console.clear();
        console.log(banner(getVersion()));
        console.log(statusLine());
        console.log(theme.dim("Conversation cleared."));
        return false;

      case "mode": {
        const name = arg as Mode;
        if (!name) {
          console.log(theme.dim("Current mode: ") + theme.primary(session.getMode()));
          console.log(theme.dim("Available: ") + MODES.join(", "));
          return false;
        }
        if (!MODES.includes(name)) {
          console.log(theme.error(`Unknown mode "${name}". Choose one of: ${MODES.join(", ")}`));
          return false;
        }
        session.setMode(name);
        config = { ...config, mode: name };
        saveConfig(config);
        console.log(theme.dim("Mode set to ") + theme.primary(name));
        return false;
      }

      case "model": {
        if (arg) {
          config = { ...config, model: arg };
          saveConfig(config);
          rebuildProvider();
          console.log(theme.dim("Model set to ") + theme.primary(config.model));
        } else {
          await chooseModel();
        }
        return false;
      }

      case "provider": {
        const name = (arg || (await ask(theme.accent(`Provider (${PROVIDER_NAMES.join(", ")}): `))).trim()) as ProviderName;
        if (!name) {
          console.log(theme.dim("Current provider: ") + theme.primary(config.provider));
          return false;
        }
        if (!PROVIDER_NAMES.includes(name)) {
          console.log(theme.error(`Unknown provider "${name}". Choose one of: ${PROVIDER_NAMES.join(", ")}`));
          return false;
        }
        // Switch provider and pick that provider's sensible default model.
        config = { ...config, provider: name, model: DEFAULT_MODELS[name] };
        saveConfig(config);
        rebuildProvider();
        console.log(
          theme.dim("Provider set to ") +
            theme.primary(config.provider) +
            theme.dim(" (model: ") +
            theme.primary(config.model) +
            theme.dim(")"),
        );
        if (name !== "ollama" && !config.apiKeys[name]) {
          console.log(
            theme.dim("No API key set. Use ") +
              theme.primary(`/apikey ${name} <key>`) +
              theme.dim(" to set it."),
          );
        }
        return false;
      }

      case "apikey": {
        const target = (rest[0] || "") as ProviderName;
        if (!PROVIDER_NAMES.includes(target) || target === "ollama") {
          console.log(
            theme.error(
              `Usage: /apikey <provider> [key]  — provider is one of: ${PROVIDER_NAMES.filter((p) => p !== "ollama").join(", ")}`,
            ),
          );
          return false;
        }
        let key = rest.slice(1).join(" ").trim();
        if (!key) {
          key = (await ask(theme.accent(`Paste ${target} API key: `))).trim();
        }
        if (!key) {
          console.log(theme.dim("No key entered; unchanged."));
          return false;
        }
        config = { ...config, apiKeys: { ...config.apiKeys, [target]: key } };
        saveConfig(config);
        if (config.provider === target) rebuildProvider();
        console.log(theme.dim(`API key for ${target} saved to config.`));
        return false;
      }

      case "editapproval": {
        const v = arg.toLowerCase();
        if (v !== "auto" && v !== "manual") {
          console.log(theme.dim("Edit approval: ") + theme.primary(config.editApproval));
          console.log(theme.dim("Usage: /editapproval auto | manual"));
          return false;
        }
        config = { ...config, editApproval: v };
        saveConfig(config);
        console.log(theme.dim("Edit approval set to ") + theme.primary(v));
        return false;
      }

      case "automode": {
        const v = arg.toLowerCase();
        if (v !== "auto" && v !== "manual") {
          console.log(theme.dim("Auto mode-switching: ") + theme.primary(config.autoMode));
          console.log(theme.dim("Usage: /automode auto | manual"));
          return false;
        }
        config = { ...config, autoMode: v };
        saveConfig(config);
        console.log(theme.dim("Auto mode-switching set to ") + theme.primary(v));
        return false;
      }

      case "compact": {
        const saved = await session.compactNow(ui);
        console.log(
          saved > 0
            ? theme.dim(`Compacted. Saved ~${saved.toLocaleString()} tokens (now ~${session.tokenCount().toLocaleString()}).`)
            : theme.dim("Nothing to compact yet."),
        );
        return false;
      }

      case "init": {
        const path = ALIRACoderPath(cwd);
        if (existsSync(path)) {
          const ok = await ui.confirm(`ALIRA_CODER.md already exists. Overwrite it?`);
          if (!ok) {
            console.log(theme.dim("Left ALIRA_CODER.md unchanged."));
            return false;
          }
        }
        writeFileSync(path, scaffoldALIRACoderMd(cwd), "utf8");
        console.log(theme.dim("Wrote ") + theme.primary("ALIRA_CODER.md") + theme.dim(". It loads automatically next session — restart or /clear to apply now."));
        return false;
      }

      case "mcp": {
        const servers = mcpStatus();
        if (!servers.length) {
          console.log(theme.dim("No MCP servers configured. Add them under \"mcpServers\" in ~/.huntercode/config.json."));
          return false;
        }
        for (const s of servers) {
          const head = s.connected ? theme.primary(`● ${s.name}`) : theme.error(`○ ${s.name}`);
          console.log(head + theme.dim(s.connected ? ` — ${s.tools.length} tools` : ` — ${s.error ?? "not connected"}`));
          for (const t of s.tools) console.log(theme.dim(`    ${t}`));
        }
        return false;
      }

      case "exit":
      case "quit":
        return true;

      default:
        console.log(theme.error(`Unknown command: /${cmd}. Try /help.`));
        return false;
    }
  };

  // Connect any configured MCP servers (non-fatal — warn and continue).
  try {
    const connected = await connectMcpServers(config);
    if (connected) console.log(theme.dim(connected));
  } catch (e) {
    console.log(theme.dim(`MCP: ${(e as Error).message}`));
  }

  // Runs one user message to completion, surfacing provider errors cleanly.
  const runUserTurn = async (message: string): Promise<boolean> => {
    try {
      await session.runTurn(message, ui);
      process.stdout.write("\n");
      return true;
    } catch (e) {
      process.stdout.write("\n");
      console.log(theme.error(`Error: ${(e as Error).message}`));
      if (config.provider === "ollama") {
        console.log(
          theme.dim(
            `Is Ollama running at ${config.ollamaUrl}? Start it with "ollama serve" and pull the model with "ollama pull ${config.model}".`,
          ),
        );
      }
      return false;
    }
  };

  // After a plan is produced (still in plan mode), offer Continue/Edit/Cancel.
  const handlePlanControls = async (): Promise<void> => {
    while (session.getMode() === "plan") {
      const choice = (
        await ask(theme.accent("→ ") + theme.primary("Plan ready. ") + theme.dim("[c] Continue  [e] Edit  [x] Cancel "))
      ).trim().toLowerCase();
      if (choice === "c" || choice === "continue") {
        session.setMode("agent");
        config = { ...config, mode: "agent" };
        saveConfig(config);
        await runUserTurn("Proceed with the plan above. Execute it step by step.");
        return;
      }
      if (choice === "e" || choice === "edit") {
        const feedback = (await ask(theme.accent("Edit") + theme.dim(" — what should change? "))).trim();
        if (!feedback) return;
        const ok = await runUserTurn(feedback);
        if (!ok) return;
        continue; // re-offer controls on the revised plan
      }
      // Cancel / anything else.
      console.log(theme.dim("Plan cancelled."));
      return;
    }
  };

  // Main REPL. The prompt owns stdin; readLine resolves null on Ctrl-C (empty
  // line) or Ctrl-D, which we treat as a clean exit.
  while (true) {
    const raw = await prompt.readLine(promptStr());
    if (raw === null) break;
    const input = raw.trim();
    if (!input) continue;

    if (input.startsWith("/")) {
      const done = await handleCommand(input);
      if (done) break;
      continue;
    }

    // Resolve @file mentions into context blocks before sending.
    const { text, warnings } = parseAttachments(input, cwd);
    for (const warn of warnings) r.notice(warn);

    const modeBefore = session.getMode();
    const ok = await runUserTurn(text);
    if (ok && modeBefore === "plan" && session.getMode() === "plan") {
      await handlePlanControls();
    }
  }

  killAll();
  closeMcpServers();
  prompt.close();
  console.log(theme.dim("Goodbye."));
  process.exit(0);
}

const fatal = (e: unknown) => {
  console.error(theme.error(`Fatal: ${(e as Error).message}`));
  process.exit(1);
};

// Subcommand dispatch: `run` (headless single task) and `serve` (HTTP API) are
// lazily imported so the interactive REPL stays the default path.
const sub = process.argv[2];
if (sub === "run") {
  import("./run.js").then((m) => m.runMain(process.argv.slice(3))).catch(fatal);
} else if (sub === "serve") {
  import("./serve.js").then((m) => m.serveMain(process.argv.slice(3))).catch(fatal);
} else {
  main().catch(fatal);
}
