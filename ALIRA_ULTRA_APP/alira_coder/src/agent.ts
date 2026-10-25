import type { Config } from "./config.js";
import type { Provider, Message } from "./types.js";
import { tools, schemasFor, toolLabel, toolResultSummary, isErrorResult } from "./tools/index.js";
import type { ToolContext } from "./tools/index.js";
import { type Mode, MODES, toolsForMode, modePromptFragment } from "./modes.js";
import { loadMemory } from "./memory.js";
import type { TodoItem } from "./ui/renderer.js";
import { maybeCompact, estimateTokens } from "./agent/compaction.js";
import { SharedMemory } from "./agent/sharedMemory.js";
import { runSubagent } from "./agent/subagent.js";

/** UI hooks the agent calls as it works. The CLI supplies these. */
export interface AgentUI {
  /** A streamed chunk of assistant text. */
  onText: (delta: string) => void;
  /** A streamed chunk of the model's reasoning/"thinking". Display-only. */
  onReasoning?: (delta: string) => void;
  /** A tool is about to run (label like "Reading main.ts"). */
  onToolCall: (label: string) => void;
  /** A tool finished — short collapsed result summary (ok=false on error). */
  onToolResult?: (summary: string, ok: boolean) => void;
  /** Print an arbitrary line (used by tools for diffs). */
  print: (line: string) => void;
  /** Show a diff block (used when an edit is auto-applied). */
  onDiff?: (diff: string) => void;
  /** Ask the user a yes/no question. */
  confirm: (question: string) => Promise<boolean>;
  /** Ask the user to approve an edit, showing its diff. Returns the decision. */
  approveEdit?: (path: string, diff: string) => Promise<"yes" | "no" | "all">;
  /** The agent updated its task list — render the todo panel. */
  onTodos?: (todos: TodoItem[]) => void;
  /** A subtle dim notice (e.g. context compaction). */
  notice?: (line: string) => void;
  /** Show (or clear, with null) an animated working indicator, e.g. "Thinking". */
  setStatus?: (label: string | null) => void;
}

const MAX_ITERATIONS = 25;

function systemPrompt(cwd: string, mode: Mode): string {
  const base = [
    "You are ALIRA Coder, an expert AI website builder integrated into ALIRA AI Assistant.",
    `You operate in the working directory: ${cwd}`,
    "",
    "Your PRIMARY mission: Build stunning, modern, fully functional websites from user voice commands.",
    "",
    "Website Building Guidelines:",
    "- Create complete, production-ready websites with index.html, styles.css, and script.js",
    "- Use modern CSS: glassmorphism, gradients, animations, flexbox/grid layouts",
    "- Add smooth scroll, AOS animations, hover effects, and interactive elements",
    "- Include responsive design — mobile-first approach always",
    "- Use Unsplash for placeholder images: https://source.unsplash.com/1600x900/?{keyword}",
    "- Add Font Awesome icons (CDN), Google Fonts, and smooth transitions",
    "- Create a README.md with project description",
    "",
    "Code Quality:",
    "- Prefer `str_replace` for editing existing files; use `write_file` for new files or full rewrites.",
    "- Read a file before editing it. Use `list_files` and `grep` to orient yourself.",
    "- Use `web_search` and `fetch_url` to consult docs when helpful.",
    "- Use `run_bash` for any shell commands needed.",
    "- Keep responses brief. Explain what you did, not what you are about to do.",
    "- When the task is complete, give a short final summary with no further tool calls.",
    "",
    "Task planning:",
    "- For any website build request, FIRST call `update_todos` to lay out the plan.",
    "- Work through tasks ONE at a time: keep exactly one task `in_progress`.",
    "- Mark tasks `completed` before starting the next one.",
    "",
    "Output format:",
    "- Always end with: DONE: <brief summary of what was built>",
    "- List all files created",
    "- If a preview URL is available, show it",
    "",
    "Choosing a mode (call `set_mode` to switch):",
    "- For website builds → use `agent` mode (full access)",
    "- For questions/analysis → use `ask` mode.",
    "",
    modePromptFragment(mode),
  ].join("\n");

  const memory = loadMemory(cwd);
  if (memory) {
    return `${base}\n\n--- PROJECT MEMORY (from past sessions) ---\n${memory}\n--- END PROJECT MEMORY ---`;
  }
  return base;
}

/** Holds conversation state for one interactive session. */
export class Session {
  private provider: Provider;
  private config: Config;
  private cwd: string;
  private mode: Mode;
  messages: Message[];
  todos: TodoItem[] = [];
  private shared = new SharedMemory();

  constructor(provider: Provider, config: Config, cwd: string) {
    this.provider = provider;
    this.config = config;
    this.cwd = cwd;
    this.mode = config.mode ?? "agent";
    this.messages = [{ role: "system", content: systemPrompt(cwd, this.mode) }];
  }

  getMode(): Mode {
    return this.mode;
  }

  getConfig(): Config {
    return this.config;
  }

  /** Switch mode, refreshing the system prompt (keeps the rest of history). */
  setMode(mode: Mode): void {
    this.mode = mode;
    this.messages[0] = { role: "system", content: systemPrompt(this.cwd, mode) };
  }

  /** Swap the active provider (e.g. after /provider) without losing history. */
  setProvider(provider: Provider, config: Config): void {
    this.provider = provider;
    this.config = config;
  }

  /** Reset conversation history, keeping the system prompt. */
  clear(): void {
    this.messages = [{ role: "system", content: systemPrompt(this.cwd, this.mode) }];
    this.todos = [];
  }

  /** Approximate current conversation size, in tokens. */
  tokenCount(): number {
    return estimateTokens(this.messages);
  }

  /** Force a context compaction now; returns tokens saved (0 if nothing to do). */
  async compactNow(ui: AgentUI): Promise<number> {
    return maybeCompact(this.messages, this.provider, this.config, ui, true);
  }

  /**
   * Run one user turn to completion: stream model output, execute any tool
   * calls allowed in the current mode, feed results back, and repeat until the
   * model stops calling tools.
   */
  async runTurn(userInput: string, ui: AgentUI): Promise<string> {
    this.messages.push({ role: "user", content: userInput });

    // Shared, per-turn edit-approval state ("yes to all" sticks for the turn).
    const approveAll = { value: this.config.editApproval === "auto" };
    // Per-turn sub-agent budget.
    let subagentCount = 0;

    const ctx: ToolContext = {
      cwd: this.cwd,
      confirm: ui.confirm,
      print: ui.print,
      stream: ui.onText,
      approveEdit: async (path, diff) => {
        if (approveAll.value) {
          ui.onDiff?.(diff);
          return "yes";
        }
        if (!ui.approveEdit) {
          // No interactive approver (headless) — apply and show.
          ui.onDiff?.(diff);
          return "yes";
        }
        const decision = await ui.approveEdit(path, diff);
        if (decision === "all") approveAll.value = true;
        return decision;
      },
      setTodos: (todos) => {
        this.todos = todos;
        ui.onTodos?.(todos);
      },
      requestModeSwitch: async (mode, reason) => {
        if (!MODES.includes(mode as Mode)) return false;
        if (this.config.autoMode === "auto") {
          ui.notice?.(`→ Switching to ${mode} mode (${reason})`);
          this.setMode(mode as Mode);
          return true;
        }
        const ok = await ui.confirm(`This looks like a ${mode} task — switch to ${mode} mode? (${reason})`);
        if (ok) this.setMode(mode as Mode);
        return ok;
      },
    };

    // Sub-agent dispatch is opt-in (config) and capped per turn.
    if (this.config.subagents.enabled) {
      ctx.spawnSubagent = async (task, context) => {
        if (subagentCount >= this.config.subagents.maxPerTurn) {
          return `Sub-agent limit reached (${this.config.subagents.maxPerTurn} per turn). Do this part yourself.`;
        }
        const id = ++subagentCount;
        ui.notice?.(`● Sub-agent ${id}: ${task}`);
        return runSubagent(id, task, context, {
          provider: this.provider,
          config: this.config,
          cwd: this.cwd,
          ui,
          shared: this.shared,
          confirm: ui.confirm,
        });
      };
    }

    let finalText = "";

    for (let i = 0; i < MAX_ITERATIONS; i++) {
      // Recompute each iteration — the mode can change mid-turn via set_mode.
      const allowed = toolsForMode(this.mode);
      const schemas = schemasFor(allowed);

      // Keep the conversation within the model's context window.
      await maybeCompact(this.messages, this.provider, this.config, ui, false);

      const status = i === 0 ? (this.mode === "plan" ? "Planning" : "Thinking") : "Working";
      ui.setStatus?.(status);
      const response = await this.provider.chatStream(
        this.messages,
        schemas,
        { model: this.config.model, temperature: this.config.temperature },
        { onText: ui.onText, onReasoning: ui.onReasoning },
      );
      ui.setStatus?.(null);

      // Surface reasoning if the provider only delivered it at the end (not
      // streamed). Streamed reasoning was already shown delta-by-delta.
      if (response.reasoning && !response.reasoningStreamed) ui.onReasoning?.(response.reasoning);

      this.messages.push({
        role: "assistant",
        content: response.content,
        toolCalls: response.toolCalls.length ? response.toolCalls : undefined,
      });

      if (!response.toolCalls.length) {
        finalText = response.content;
        break;
      }

      for (const call of response.toolCalls) {
        ui.onToolCall(toolLabel(call.name, call.arguments));
        let result: string;
        const tool = tools[call.name];
        if (!tool) {
          result = `Error: unknown tool "${call.name}".`;
        } else if (!allowed.includes(call.name)) {
          result = `Error: the "${call.name}" tool is not available in ${this.mode} mode (read-only). Switch to agent mode to make changes.`;
        } else {
          try {
            result = await tool.execute(call.arguments, ctx);
          } catch (e) {
            result = `Error executing ${call.name}: ${(e as Error).message}`;
          }
        }
        const ok = !isErrorResult(result);
        ui.onToolResult?.(toolResultSummary(call.name, result, ok), ok);
        this.messages.push({
          role: "tool",
          content: result,
          toolCallId: call.id,
          name: call.name,
        });
      }
    }

    return finalText;
  }
}
