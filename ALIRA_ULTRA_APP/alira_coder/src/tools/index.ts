import type { ToolSchema } from "../types.js";
import type { Tool } from "./types.js";
import { readFileTool } from "./read_file.js";
import { writeFileTool } from "./write_file.js";
import { strReplaceTool } from "./str_replace.js";
import { listFilesTool } from "./list_files.js";
import { runBashTool } from "./run_bash.js";
import { grepTool } from "./grep.js";
import { webSearchTool } from "./web_search.js";
import { fetchUrlTool } from "./fetch_url.js";
import { saveMemoryTool } from "./save_memory.js";
import { checkLogsTool, stopProcessTool } from "./manage_process.js";
import { updateTodosTool } from "./update_todos.js";
import { setModeTool } from "./set_mode.js";
import { rememberTool } from "./remember.js";
import { spawnSubagentTool } from "./spawn_subagent.js";

export type { Tool, ToolContext } from "./types.js";

/** The agent's full toolset, keyed by tool name. */
export const tools: Record<string, Tool> = {
  read_file: readFileTool,
  write_file: writeFileTool,
  str_replace: strReplaceTool,
  list_files: listFilesTool,
  run_bash: runBashTool,
  check_logs: checkLogsTool,
  stop_process: stopProcessTool,
  grep: grepTool,
  web_search: webSearchTool,
  fetch_url: fetchUrlTool,
  save_memory: saveMemoryTool,
  update_todos: updateTodosTool,
  set_mode: setModeTool,
  remember: rememberTool,
  spawn_subagent: spawnSubagentTool,
};

/** Names of tools registered at runtime (e.g. MCP) — allowed in agent mode. */
export const dynamicAgentTools = new Set<string>();

/** Tools registered at runtime (e.g. from MCP servers). Merged into `tools`. */
export function registerTool(tool: Tool): void {
  tools[tool.schema.name] = tool;
  dynamicAgentTools.add(tool.schema.name);
}

/** Resolve a set of tool names to their internal schemas (for the provider). */
export function schemasFor(names: string[]): ToolSchema[] {
  return names.map((n) => tools[n]?.schema).filter((s): s is ToolSchema => Boolean(s));
}

/** A short human-readable label for a tool call, e.g. "Reading main.ts". */
export function toolLabel(name: string, args: Record<string, any>): string {
  switch (name) {
    case "read_file":
      return `Reading ${args.path}`;
    case "write_file":
      return `Writing ${args.path}`;
    case "str_replace":
      return `Editing ${args.path}`;
    case "list_files":
      return `Listing ${args.path ?? "."}`;
    case "run_bash":
      return args.background ? `Running (background): ${args.command}` : `Running: ${args.command}`;
    case "check_logs":
      return args.id === undefined ? "Listing background processes" : `Checking logs #${args.id}`;
    case "stop_process":
      return `Stopping process #${args.id}`;
    case "grep":
      return `Searching for /${args.pattern}/`;
    case "web_search":
      return `Web search: ${args.query}`;
    case "fetch_url":
      return `Fetching ${args.url}`;
    case "save_memory":
      return `Saving to memory: ${args.title}`;
    case "update_todos":
      return "Updating tasks";
    case "set_mode":
      return `Switching to ${args.mode} mode`;
    case "remember":
      return "Noting to project memory";
    case "spawn_subagent":
      return `Sub-agent: ${args.task}`;
    default:
      return name;
  }
}

/**
 * A short, human-readable summary of a tool's RESULT, shown as the collapsed
 * "  └ …" line beneath the action. Derived from the tool's return string,
 * which already encodes the outcome; we just compress it to one tidy line.
 */
export function toolResultSummary(name: string, result: string, ok: boolean): string {
  if (!ok) {
    // Surface the first line of the error, trimmed.
    return truncate(result.replace(/^Error[:e]?\s*/i, "").split("\n")[0] || "failed", 120);
  }
  const first = result.split("\n")[0].trim();
  switch (name) {
    case "read_file": {
      const m = result.match(/of (\d+)\)/) || result.match(/(\d+)\s+lines?/);
      const lines = m ? Number(m[1]) : result.split("\n").length;
      return `Read ${lines} line${lines === 1 ? "" : "s"}`;
    }
    case "str_replace":
      return "Edited" + (/\((.*?)\)/.exec(first)?.[0] ? " " + /\((.*?)\)/.exec(first)![0] : "");
    case "write_file":
      return truncate(first, 100);
    case "run_bash":
      return truncate(first || "Done", 120);
    default:
      return truncate(first || "Done", 120);
  }
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

/** Whether a tool's return string represents an error (used for ok/failed UI). */
export function isErrorResult(result: string): boolean {
  return /^Error\b/i.test(result.trim());
}
