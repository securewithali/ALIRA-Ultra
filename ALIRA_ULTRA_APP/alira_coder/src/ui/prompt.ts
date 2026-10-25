import * as readline from "node:readline";
import { theme } from "./theme.js";
import { applySuggestion, isComplete, type Suggestion } from "../commands.js";

/**
 * A tiny raw-mode line editor with a live, navigable autocomplete dropdown —
 * no dependencies, built on Node's keypress events. It replaces readline so the
 * dropdown can own ↑/↓/Tab/Enter without fighting readline's history handling.
 *
 * `readLine` powers the main prompt (with the dropdown); `question` is a plain
 * line read (no menu) for confirmations and sub-prompts. On non-TTY stdin both
 * degrade to a simple readline-based read.
 */

export interface PromptOptions {
  /** Returns the suggestions for the current line (empty → no menu). */
  completions: (line: string) => Suggestion[];
}

export interface Prompt {
  /** Main prompt with live autocomplete. Resolves null on Ctrl-C/Ctrl-D (exit). */
  readLine(promptText: string): Promise<string | null>;
  /** Plain line read (no menu). Resolves "" if cancelled. */
  question(promptText: string): Promise<string>;
  close(): void;
}

const MAX_ROWS = 8;
const ANSI_RE = /\x1b\[[0-9;]*m/g;
const stripAnsi = (s: string) => s.replace(ANSI_RE, "");
const visibleWidth = (s: string) => stripAnsi(s).length;

export function createPrompt(opts: PromptOptions): Prompt {
  const stdin = process.stdin;
  const stdout = process.stdout;
  const isTTY = Boolean(stdin.isTTY);
  const history: string[] = [];

  if (isTTY) readline.emitKeypressEvents(stdin);

  // ---- Non-TTY fallback (piped input): queue lines so none are dropped
  // between reads (rl.question in a loop can lose buffered lines). No menu. ----
  let fallbackRl: readline.Interface | null = null;
  const pending: string[] = [];
  let waiter: ((v: string | null) => void) | null = null;
  let closed = false;
  function ensureFallback() {
    if (fallbackRl) return;
    fallbackRl = readline.createInterface({ input: stdin });
    fallbackRl.on("line", (l) => {
      if (waiter) {
        const w = waiter;
        waiter = null;
        w(l);
      } else {
        pending.push(l);
      }
    });
    fallbackRl.on("close", () => {
      closed = true;
      if (waiter) {
        const w = waiter;
        waiter = null;
        w(null);
      }
    });
  }
  function readPiped(promptText: string): Promise<string | null> {
    ensureFallback();
    if (promptText) stdout.write(promptText);
    return new Promise((resolve) => {
      if (pending.length) return resolve(pending.shift() as string);
      if (closed) return resolve(null);
      waiter = resolve;
    });
  }

  // ---- TTY interactive reader. ----
  function readTTY(promptText: string, withMenu: boolean): Promise<string | null> {
    return new Promise((resolve) => {
      let line = "";
      let cursor = 0;
      let start = 0; // horizontal scroll offset (keeps the input on one row)
      let selected = 0;
      let dismissed = false; // Esc closes the menu until the line changes
      let navigated = false; // did the user move the selection with ↑/↓?
      let lastRows = 0;

      let histIndex = history.length;
      let stash = "";

      const suggestionsNow = (): Suggestion[] =>
        withMenu && !dismissed ? opts.completions(line) : [];

      const buildRows = (suggestions: Suggestion[]): string[] => {
        const cols = stdout.columns || 80;
        return suggestions.slice(0, MAX_ROWS).map((s, i) => {
          const label = (s.isCommand ? "/" : "") + s.value;
          let desc = s.description ?? "";
          // Keep each row on one terminal line (so cursor math stays correct).
          const budget = cols - label.length - 4;
          if (desc && budget < desc.length) {
            desc = budget > 1 ? desc.slice(0, Math.max(0, budget - 1)) + "…" : "";
          }
          if (i === selected) {
            return (
              theme.accent("❯ ") +
              theme.primary(label) +
              (desc ? theme.dim("  " + desc) : "")
            );
          }
          return "  " + theme.dim(label) + (desc ? theme.dim("  " + desc) : "");
        });
      };

      const render = () => {
        const suggestions = suggestionsNow();
        if (selected >= suggestions.length) selected = Math.max(0, suggestions.length - 1);
        const rows = buildRows(suggestions);

        // Keep the input on a single terminal row by scrolling horizontally,
        // so a line longer than the terminal width never wraps.
        const cols = stdout.columns || 80;
        const promptW = visibleWidth(promptText);
        const avail = Math.max(8, cols - promptW - 1);
        if (cursor < start) start = cursor;
        else if (cursor >= start + avail) start = cursor - avail + 1;
        if (start < 0) start = 0;
        const visible = line.slice(start, start + avail);

        let out = "\r\x1b[0J" + promptText + visible;
        if (rows.length) out += "\n" + rows.join("\n");
        // Move the cursor back up to the input line and to the right column.
        if (rows.length) out += `\x1b[${rows.length}A`;
        out += "\r";
        const col = promptW + (cursor - start);
        if (col > 0) out += `\x1b[${col}C`;
        stdout.write(out);
        lastRows = rows.length;
      };

      const cleanup = () => {
        stdin.removeListener("keypress", onKey);
        if (stdin.isTTY) stdin.setRawMode(false);
        stdin.pause();
      };

      const finish = (result: string | null) => {
        cleanup();
        // Redraw the line without the menu, then drop to a fresh line.
        stdout.write("\r\x1b[0J" + promptText + line + "\n");
        if (withMenu && result && result.trim()) history.push(result);
        resolve(result);
      };

      const historyPrev = () => {
        if (!history.length) return;
        if (histIndex === history.length) stash = line;
        if (histIndex > 0) histIndex--;
        line = history[histIndex];
        cursor = line.length;
        render();
      };
      const historyNext = () => {
        if (histIndex < history.length) histIndex++;
        line = histIndex === history.length ? stash : history[histIndex];
        cursor = line.length;
        render();
      };

      const onKey = (str: string, key: readline.Key | undefined) => {
        const k = key ?? ({} as readline.Key);
        const name = k.name;

        if (name === "return" || name === "enter") {
          const suggestions = suggestionsNow();
          if (suggestions.length) {
            const choice = suggestions[selected];
            line = applySuggestion(line, choice);
            cursor = line.length;
            navigated = false;
            selected = 0;
            // No-arg command or an argument value → run it now. A command that
            // takes an argument just expands and waits for the argument.
            if (isComplete(choice)) {
              finish(line);
            } else {
              render();
            }
            return;
          }
          finish(line);
          return;
        }

        if (k.ctrl && name === "c") {
          if (line.length === 0) finish(null);
          else {
            line = "";
            cursor = 0;
            dismissed = false;
            selected = 0;
            navigated = false;
            render();
          }
          return;
        }

        if (k.ctrl && name === "d") {
          if (line.length === 0) {
            finish(null);
            return;
          }
          line = line.slice(0, cursor) + line.slice(cursor + 1);
          render();
          return;
        }

        if (name === "tab") {
          const suggestions = suggestionsNow();
          if (suggestions.length) {
            line = applySuggestion(line, suggestions[selected]);
            cursor = line.length;
            selected = 0;
            navigated = false;
            dismissed = false;
            render();
          }
          return;
        }

        if (name === "escape") {
          dismissed = true;
          render();
          return;
        }

        if (name === "up") {
          const suggestions = suggestionsNow();
          if (suggestions.length) {
            selected = (selected - 1 + suggestions.length) % suggestions.length;
            navigated = true;
            render();
          } else if (withMenu) {
            historyPrev();
          }
          return;
        }

        if (name === "down") {
          const suggestions = suggestionsNow();
          if (suggestions.length) {
            selected = (selected + 1) % suggestions.length;
            navigated = true;
            render();
          } else if (withMenu) {
            historyNext();
          }
          return;
        }

        if (name === "left") {
          if (cursor > 0) cursor--;
          render();
          return;
        }
        if (name === "right") {
          if (cursor < line.length) cursor++;
          render();
          return;
        }
        if (name === "home" || (k.ctrl && name === "a")) {
          cursor = 0;
          render();
          return;
        }
        if (name === "end" || (k.ctrl && name === "e")) {
          cursor = line.length;
          render();
          return;
        }
        if (k.ctrl && name === "u") {
          line = line.slice(cursor);
          cursor = 0;
          dismissed = false;
          selected = 0;
          render();
          return;
        }
        if (name === "backspace") {
          if (cursor > 0) {
            line = line.slice(0, cursor - 1) + line.slice(cursor);
            cursor--;
            dismissed = false;
            selected = 0;
            navigated = false;
            render();
          }
          return;
        }
        if (name === "delete") {
          line = line.slice(0, cursor) + line.slice(cursor + 1);
          render();
          return;
        }

        // Printable input (including pasted text without control chars).
        if (str && !k.ctrl && !k.meta && isPrintable(str)) {
          line = line.slice(0, cursor) + str + line.slice(cursor);
          cursor += str.length;
          dismissed = false;
          selected = 0;
          navigated = false;
          render();
        }
      };

      if (stdin.isTTY) stdin.setRawMode(true);
      stdin.resume();
      stdin.on("keypress", onKey);
      render();
    });
  }

  return {
    readLine: (p) => (isTTY ? readTTY(p, true) : readPiped(p)),
    question: (p) =>
      (isTTY ? readTTY(p, false) : readPiped(p)).then((v) => v ?? ""),
    close: () => {
      if (isTTY && stdin.isTTY && stdin.isRaw) stdin.setRawMode(false);
      fallbackRl?.close();
    },
  };
}

function isPrintable(str: string): boolean {
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i);
    if (c < 32 || c === 127) return false;
  }
  return true;
}
