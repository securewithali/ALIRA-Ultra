import { appendFileSync } from "node:fs";
import type { AgentUI } from "./agent.js";

/**
 * Progress channel for headless callers (e.g. Maya).
 *
 * The interactive renderer already surfaces tool actions, results, the todo
 * panel, and notices. This taps those same `AgentUI` events and emits them as
 * structured `ProgressEvent`s so an automated caller can show live progress:
 *  - `huntercode run --progress-file <path>` appends newline-delimited JSON.
 *  - `huntercode serve` buffers events per session for `GET /session/:id/progress`.
 *
 * It is purely additive — it wraps an existing `AgentUI` and forwards every call
 * unchanged, so the human-facing output is identical.
 */

export interface ProgressEvent {
  /** Epoch milliseconds. */
  t: number;
  /** One of: started | tool | tool_result | todos | notice | done | error. */
  type: string;
  [key: string]: unknown;
}

export interface ProgressSink {
  emit(type: string, data?: Record<string, unknown>): void;
}

/** A no-op sink (when no progress channel is requested). */
export const nullProgressSink: ProgressSink = { emit() {} };

/** Append each event as one JSON line to `path`. Best-effort (never throws). */
export function fileProgressSink(path: string): ProgressSink {
  return {
    emit(type, data) {
      try {
        appendFileSync(path, JSON.stringify({ t: Date.now(), type, ...(data ?? {}) }) + "\n", "utf8");
      } catch {
        /* best-effort: a progress write must never break the task */
      }
    },
  };
}

/** Collect events into an in-memory array (used by `serve`'s poll endpoint). */
export function bufferProgressSink(buffer: ProgressEvent[], cap = 1000): ProgressSink {
  return {
    emit(type, data) {
      buffer.push({ t: Date.now(), type, ...(data ?? {}) });
      // Soft cap: drop oldest if a single turn somehow floods (offsets reset
      // per message in serve, so this rarely triggers).
      if (buffer.length > cap) buffer.splice(0, buffer.length - cap);
    },
  };
}

/**
 * Wrap an `AgentUI` so every meaningful event is also emitted to `sink`. The
 * original UI behavior is preserved exactly; this only adds the side-channel.
 */
export function withProgress(ui: AgentUI, sink: ProgressSink): AgentUI {
  return {
    ...ui,
    onToolCall: (label) => {
      sink.emit("tool", { label });
      ui.onToolCall(label);
    },
    onToolResult: (summary, ok) => {
      sink.emit("tool_result", { summary, ok });
      ui.onToolResult?.(summary, ok);
    },
    onTodos: (todos) => {
      sink.emit("todos", { todos });
      ui.onTodos?.(todos);
    },
    notice: (line) => {
      sink.emit("notice", { text: line });
      ui.notice?.(line);
    },
  };
}
