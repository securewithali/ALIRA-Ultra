import type { ToolSchema } from "../types.js";
import type { TodoItem } from "../ui/renderer.js";

/** Runtime context handed to every tool's `execute`. */
export interface ToolContext {
  /** The working directory the session is scoped to. */
  cwd: string;
  /** Ask the user a yes/no question (used before destructive actions). */
  confirm: (question: string) => Promise<boolean>;
  /** Print a line to the UI (e.g. a colored diff). */
  print: (line: string) => void;
  /** Stream raw output to the UI as it arrives (no trailing newline added). */
  stream?: (chunk: string) => void;
  /**
   * Show a diff and obtain approval before applying an edit. Honors the
   * `editApproval` setting: "auto" applies (still showing the diff), "manual"
   * prompts y/n/a. Returns the decision; tools must not write on "no".
   */
  approveEdit: (path: string, diff: string) => Promise<"yes" | "no" | "all">;
  /** Replace the session's task list and re-render the todo panel. */
  setTodos: (todos: TodoItem[]) => void;
  /** Request a mode switch; resolves true if the switch happened. */
  requestModeSwitch: (mode: string, reason: string) => Promise<boolean>;
  /** Dispatch a sub-agent for an isolated sub-task (Phase 3.1). */
  spawnSubagent?: (task: string, context?: string) => Promise<string>;
}

export interface Tool {
  schema: ToolSchema;
  /** Execute the tool and return a string result fed back to the model. */
  execute: (args: Record<string, any>, ctx: ToolContext) => Promise<string>;
}
