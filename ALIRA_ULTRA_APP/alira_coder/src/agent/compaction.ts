import type { Config } from "../config.js";
import type { Message, Provider } from "../types.js";
import type { AgentUI } from "../agent.js";

/**
 * Context compaction — keeps long sessions (and sub-agents) under the model's
 * context window by summarizing the OLDER part of the conversation into a
 * single compact note, preserving the system prompt and the most recent turns
 * verbatim. Triggered automatically near a threshold, or on demand via /compact.
 */

/** Number of recent user turns kept verbatim (with everything after them). */
const KEEP_RECENT_TURNS = 3;

/** Rough per-model context windows (tokens). Matched by substring; safe default. */
const CONTEXT_WINDOWS: { match: RegExp; window: number }[] = [
  { match: /claude/i, window: 200_000 },
  { match: /gemini/i, window: 1_000_000 },
  { match: /gpt-oss|nemotron|llama|qwen|deepseek|mistral|codestral/i, window: 128_000 },
];
const DEFAULT_WINDOW = 32_000;

export function contextWindow(model: string): number {
  for (const { match, window } of CONTEXT_WINDOWS) if (match.test(model)) return window;
  return DEFAULT_WINDOW;
}

/** Cheap token estimate: ~4 chars/token across all message content. */
export function estimateTokens(messages: Message[]): number {
  let chars = 0;
  for (const m of messages) {
    chars += (m.content?.length ?? 0) + 8;
    if (m.toolCalls) chars += JSON.stringify(m.toolCalls).length;
  }
  return Math.ceil(chars / 4);
}

/** Compact a one-line serialization of a message span for the summarizer. */
function serialize(messages: Message[]): string {
  return messages
    .map((m) => {
      if (m.role === "tool") return `tool(${m.name ?? ""}): ${truncate(m.content, 400)}`;
      if (m.role === "assistant" && m.toolCalls?.length) {
        const calls = m.toolCalls.map((c) => `${c.name}(${JSON.stringify(c.arguments)})`).join(", ");
        return `assistant: ${m.content || ""} [calls: ${truncate(calls, 300)}]`;
      }
      return `${m.role}: ${truncate(m.content, 800)}`;
    })
    .join("\n");
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

/**
 * Summarize older messages and splice the summary into the conversation in
 * place. Returns the number of tokens saved (0 if nothing was compacted).
 *
 * @param force  when true, compact regardless of the threshold (for /compact).
 */
export async function maybeCompact(
  messages: Message[],
  provider: Provider,
  config: Config,
  ui: AgentUI,
  force: boolean,
): Promise<number> {
  const before = estimateTokens(messages);
  if (!force) {
    const limit = contextWindow(config.model) * Math.min(Math.max(config.compactThreshold, 0.1), 0.95);
    if (before < limit) return 0;
  }

  // Cut at a real user turn (role 'user', not a tool result) so we never split
  // a tool-call/result pair. Keep the last KEEP_RECENT_TURNS user turns.
  const userTurns: number[] = [];
  for (let i = 1; i < messages.length; i++) if (messages[i].role === "user") userTurns.push(i);
  if (userTurns.length <= KEEP_RECENT_TURNS + 1) return 0;

  const cut = userTurns[userTurns.length - KEEP_RECENT_TURNS];
  const head = messages.slice(1, cut);
  if (!head.length) return 0;

  let summary: string;
  try {
    const res = await provider.chat(
      [
        {
          role: "system",
          content:
            "You compress conversation history for a coding agent. Preserve goals, decisions, file paths touched, commands run, and any OPEN tasks. Drop pleasantries and redundancy. Output a tight bulleted summary, no preamble.",
        },
        { role: "user", content: "Summarize this earlier conversation excerpt:\n\n" + serialize(head) },
      ],
      [],
      { model: config.model, temperature: 0 },
    );
    summary = res.content.trim();
  } catch {
    return 0; // summarizer failed — leave history intact rather than lose it.
  }
  if (!summary) return 0;

  // Remove the head and prepend the summary onto the first kept user message,
  // keeping message roles valid for every provider.
  messages.splice(1, cut - 1);
  const first = messages[1];
  messages[1] = {
    ...first,
    content: `(Summary of earlier conversation)\n${summary}\n\n${first.content}`,
  };

  const saved = before - estimateTokens(messages);
  if (saved > 0) ui.notice?.(`↺ Compacted context (saved ~${saved.toLocaleString()} tokens)`);
  return Math.max(0, saved);
}
