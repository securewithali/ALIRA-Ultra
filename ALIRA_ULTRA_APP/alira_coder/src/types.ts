/**
 * Shared, provider-agnostic types.
 *
 * Everything in the agent works with these normalized shapes. Each provider is
 * responsible for translating to/from its own wire format, so the agent loop
 * never needs to know which backend is in use.
 */

export type Role = "system" | "user" | "assistant" | "tool";

/** A JSON Schema object describing a tool's parameters. */
export interface JSONSchema {
  type: "object";
  properties: Record<string, unknown>;
  required?: string[];
  [key: string]: unknown;
}

/** The single internal definition of a tool, adapted per-provider. */
export interface ToolSchema {
  name: string;
  description: string;
  parameters: JSONSchema;
}

/** A normalized tool call requested by the model. */
export interface ToolCall {
  /** Provider-supplied id, or a synthesized one when the provider omits it. */
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

/** A single message in the conversation history. */
export interface Message {
  role: Role;
  /** Plain-text content (may be empty when the turn is purely tool calls). */
  content: string;
  /** Present on assistant messages that requested tool execution. */
  toolCalls?: ToolCall[];
  /** Present on `tool` messages: the id of the call this result answers. */
  toolCallId?: string;
  /** Present on `tool` messages: the name of the tool that produced this. */
  name?: string;
}

/** Approximate token usage for one model turn, when the provider reports it. */
export interface Usage {
  promptTokens?: number;
  completionTokens?: number;
}

/** A normalized response from a single model turn. */
export interface ChatResponse {
  /** Assistant text content. */
  content: string;
  /** Any tool calls the model requested, normalized. */
  toolCalls: ToolCall[];
  /** Reasoning/"thinking" trace, when the model exposes one (e.g. DeepSeek-R1).
   *  Display-only — never sent back as conversation history. */
  reasoning?: string;
  /** Token usage for this turn, when reported. Used by context compaction. */
  usage?: Usage;
  /** True when the reasoning trace was already streamed via callbacks (so the
   *  caller should not re-render `reasoning` as a block). */
  reasoningStreamed?: boolean;
  /** The raw provider payload, for debugging. */
  raw?: unknown;
}

export interface ChatOptions {
  model: string;
  temperature?: number;
  signal?: AbortSignal;
}

/** Called with each streamed text delta as it arrives. */
export type StreamHandler = (delta: string) => void;

/**
 * Streaming sinks handed to `chatStream`. `onText` receives assistant text
 * deltas; `onReasoning` (optional) receives reasoning/"thinking" deltas for
 * models that expose a live trace. A bare function is also accepted for
 * backward-compatibility and treated as `onText`.
 */
export interface StreamCallbacks {
  onText: (delta: string) => void;
  onReasoning?: (delta: string) => void;
}

/** Normalize the `chatStream` callback arg into a `StreamCallbacks` object. */
export function toStreamCallbacks(cb: StreamHandler | StreamCallbacks): StreamCallbacks {
  return typeof cb === "function" ? { onText: cb } : cb;
}

/**
 * The contract every LLM backend implements. Adding a new backend means
 * implementing this interface; nothing else in the agent changes.
 */
export interface Provider {
  readonly name: string;

  /** Non-streaming chat. */
  chat(
    messages: Message[],
    tools: ToolSchema[],
    opts: ChatOptions,
  ): Promise<ChatResponse>;

  /** Streaming chat. Text/reasoning deltas go to the callbacks; the resolved
   *  value is the fully-assembled, normalized response (including any tool
   *  calls). Accepts a bare `onText` function or a `StreamCallbacks` object. */
  chatStream(
    messages: Message[],
    tools: ToolSchema[],
    opts: ChatOptions,
    onDelta: StreamHandler | StreamCallbacks,
  ): Promise<ChatResponse>;

  /** Optionally list models available from this backend (e.g. Ollama tags). */
  listModels?(): Promise<string[]>;
}
