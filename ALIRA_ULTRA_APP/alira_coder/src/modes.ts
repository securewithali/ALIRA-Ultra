/**
 * Operating modes. A mode gates which tools are available and shapes the
 * system prompt — the agent loop itself stays the same across modes.
 */
import { dynamicAgentTools } from "./tools/index.js";

export type Mode = "agent" | "plan" | "ask";

export const MODES: Mode[] = ["agent", "plan", "ask"];

/**
 * Control tools that aren't file mutations (planning + self-direction), so they
 * are available in every mode. `set_mode` is how the agent can escalate from a
 * read-only mode to `agent`.
 */
export const CONTROL_TOOLS = ["update_todos", "set_mode"];

/** Read-only tools: safe in every mode. */
export const READ_ONLY_TOOLS = [
  "read_file",
  "list_files",
  "grep",
  "web_search",
  "fetch_url",
];

/** Full toolset for agent mode (read-only + mutating + memory). */
export const AGENT_TOOLS = [
  ...READ_ONLY_TOOLS,
  "write_file",
  "str_replace",
  "run_bash",
  "check_logs",
  "stop_process",
  "save_memory",
  "remember",
  "spawn_subagent",
];

/** The tool names allowed in a given mode (incl. runtime/MCP tools in agent). */
export function toolsForMode(mode: Mode): string[] {
  const base = mode === "agent" ? AGENT_TOOLS : READ_ONLY_TOOLS;
  const dynamic = mode === "agent" ? [...dynamicAgentTools] : [];
  return [...base, ...CONTROL_TOOLS, ...dynamic];
}

/** Mode-specific guidance appended to the system prompt. */
export function modePromptFragment(mode: Mode): string {
  switch (mode) {
    case "plan":
      return [
        "MODE: PLAN (read-only).",
        "Investigate the code using your read-only tools, then produce a clear,",
        "step-by-step implementation plan. Do NOT modify files or run commands —",
        "those tools are unavailable in this mode. End with the proposed plan.",
      ].join("\n");
    case "ask":
      return [
        "MODE: ASK (read-only).",
        "Answer the user's question about the code, documentation, or the web.",
        "Use read-only tools (and web search / fetch) to ground your answer.",
        "Do NOT modify files or run commands.",
      ].join("\n");
    case "agent":
    default:
      return [
        "MODE: AGENT.",
        "You may read, search, edit, and write files, and run shell commands to",
        "complete the task. After finishing a non-trivial fix, call `save_memory`",
        "with a short title and a summary of what the issue was and how you fixed",
        "it, so future sessions have that context.",
      ].join("\n");
  }
}
