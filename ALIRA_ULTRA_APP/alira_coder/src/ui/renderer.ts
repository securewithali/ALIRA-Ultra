import { theme } from "./theme.js";

/**
 * The single owner of terminal output.
 *
 * Every visible thing the agent does — streamed text, reasoning, live tool
 * action lines, collapsed results, diffs, the todo panel, status spinner —
 * goes through one Renderer so output stays consistent and composable. It is
 * intentionally a linear-scrollback model (no full TUI): it only redraws in
 * place for the spinner and the todo panel, which keeps it dependency-free and
 * robust. Interactive prompts (confirm / choice) live in the CLI layer, which
 * owns stdin; the renderer is output-only.
 *
 * On a non-TTY stream (e.g. `huntercode run`) the spinner and in-place redraws
 * are disabled but all content still prints, so headless logs stay readable.
 */

export type TodoStatus = "pending" | "in_progress" | "completed" | "failed";

export interface TodoItem {
  id: string;
  content: string;
  status: TodoStatus;
}

const TODO_GLYPH: Record<TodoStatus, (s: string) => string> = {
  pending: (s) => theme.dim(s),
  in_progress: (s) => theme.accent(s),
  completed: (s) => theme.added(s),
  failed: (s) => theme.error(s),
};

const TODO_MARK: Record<TodoStatus, string> = {
  pending: "○",
  in_progress: "◐",
  completed: "✔",
  failed: "✗",
};

const SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"];

export interface Renderer {
  /** Stream a chunk of assistant text. */
  text(delta: string): void;
  /** Stream a chunk of reasoning/"thinking" (opens a dim block on first call). */
  reasoning(delta: string): void;
  /** A tool is starting — prints the live action line (e.g. "→ Reading x.ts"). */
  toolStart(label: string): void;
  /** A tool finished — prints the collapsed "  └ <summary>" result line. */
  toolEnd(summary: string, ok?: boolean): void;
  /** Show (or clear, with null) the animated working indicator. */
  status(label: string | null): void;
  /** Print a raw line as-is. */
  print(line: string): void;
  /** Print a (already-colored) diff block, indented for readability. */
  diff(text: string): void;
  /** Render the todo panel, redrawing in place when possible. */
  todos(list: TodoItem[]): void;
  /** A subtle dim one-line notice (e.g. context compaction). */
  notice(line: string): void;
  /** Render a nested sub-agent panel header + its task lines. */
  subagentPanel(task: string, todos: TodoItem[]): void;
  /** Ensure the cursor is at the start of a fresh line (used before prompts). */
  flushLine(): void;
}

export function createRenderer(stream: NodeJS.WriteStream = process.stdout): Renderer {
  const isTTY = Boolean(stream.isTTY);
  let atLineStart = true;
  let reasoningOpen = false;
  let spinTimer: NodeJS.Timeout | null = null;
  let lastTodoLines = 0; // for in-place redraw of the todo panel

  const w = (s: string) => {
    if (!s) return;
    stream.write(s);
    atLineStart = s.endsWith("\n");
  };

  const clearStatus = () => {
    if (spinTimer) {
      clearInterval(spinTimer);
      spinTimer = null;
      if (isTTY) stream.write("\r\x1b[2K");
      atLineStart = true;
    }
  };

  const ensureNewline = () => {
    if (!atLineStart) w("\n");
  };

  const closeReasoning = () => {
    if (reasoningOpen) {
      w("\n");
      reasoningOpen = false;
    }
  };

  return {
    text(delta) {
      clearStatus();
      closeReasoning();
      lastTodoLines = 0;
      w(delta);
    },

    reasoning(delta) {
      if (!delta) return;
      clearStatus();
      lastTodoLines = 0;
      if (!reasoningOpen) {
        ensureNewline();
        w(theme.dim("💭 thinking") + "\n");
        reasoningOpen = true;
      }
      w(theme.dim(delta));
    },

    toolStart(label) {
      clearStatus();
      closeReasoning();
      ensureNewline();
      lastTodoLines = 0;
      w(theme.toolCall(label) + "\n");
    },

    toolEnd(summary, ok = true) {
      if (!summary) return;
      ensureNewline();
      const body = ok ? theme.dim(summary) : theme.error(summary);
      w(theme.dim("  └ ") + body + "\n");
    },

    status(label) {
      if (!isTTY || !label) {
        clearStatus();
        return;
      }
      closeReasoning();
      ensureNewline();
      if (spinTimer) clearInterval(spinTimer);
      let i = 0;
      const draw = () => {
        stream.write(
          "\r\x1b[2K" + theme.accent(SPINNER[i % SPINNER.length]) + " " + theme.dim(label + "…"),
        );
        atLineStart = false;
        i++;
      };
      draw();
      spinTimer = setInterval(draw, 80);
    },

    print(line) {
      clearStatus();
      closeReasoning();
      ensureNewline();
      lastTodoLines = 0;
      w(line + "\n");
    },

    diff(text) {
      clearStatus();
      closeReasoning();
      ensureNewline();
      lastTodoLines = 0;
      for (const line of text.split("\n")) w("  " + line + "\n");
    },

    todos(list) {
      clearStatus();
      closeReasoning();
      const lines = renderTodoLines(list, "");
      // Redraw in place if the panel was the last thing printed (TTY only).
      if (isTTY && lastTodoLines > 0 && atLineStart) {
        stream.write(`\x1b[${lastTodoLines}A\x1b[0J`);
      } else {
        ensureNewline();
      }
      for (const l of lines) w(l + "\n");
      lastTodoLines = lines.length;
    },

    notice(line) {
      clearStatus();
      closeReasoning();
      ensureNewline();
      lastTodoLines = 0;
      w(theme.dim(line) + "\n");
    },

    subagentPanel(task, todos) {
      clearStatus();
      closeReasoning();
      ensureNewline();
      lastTodoLines = 0;
      w(theme.accent("● ") + theme.primary("Sub-agent: " + task) + "\n");
      for (const l of renderTodoLines(todos, "  ")) w(l + "\n");
    },

    flushLine() {
      clearStatus();
      closeReasoning();
      ensureNewline();
    },
  };
}

function renderTodoLines(list: TodoItem[], indent: string): string[] {
  const lines: string[] = [];
  lines.push(indent + theme.bold("Tasks"));
  for (const t of list) {
    const color = TODO_GLYPH[t.status] ?? theme.dim;
    const mark = TODO_MARK[t.status] ?? "○";
    const text = t.status === "completed" ? theme.dim(t.content) : t.content;
    lines.push(indent + color(mark) + " " + text);
  }
  return lines;
}
