import type {
  ChatOptions,
  ChatResponse,
  Message,
  Provider,
  StreamCallbacks,
  StreamHandler,
  ToolCall,
  ToolSchema,
} from "../types.js";
import { toStreamCallbacks } from "../types.js";
import { sseLines, ToolCallAccumulator } from "./sse.js";

/**
 * NVIDIA provider (build.nvidia.com / NIM).
 *
 * NVIDIA exposes an OpenAI-compatible `/chat/completions` API at
 * `integrate.api.nvidia.com`, so this mirrors the OpenRouter provider. Many
 * models have a usable free tier with a `nvapi-...` key. Key-guarded; streaming
 * is buffered (see Anthropic note).
 *
 * Reasoning ("thinking"): reasoning-capable models (e.g. DeepSeek-R1) expose
 * their trace either as a `reasoning_content` field on the message or inline as
 * a leading `<think>...</think>` block in the content. We surface it as
 * `ChatResponse.reasoning` (display-only) and keep `content` clean.
 *
 * Format notes (same as OpenRouter):
 *  - tools use the `{type:'function', function:{...}}` envelope;
 *  - tool-call arguments come back as a JSON *string* that must be parsed;
 *  - tool results are `{role:'tool', tool_call_id, content}` messages.
 */
export class NvidiaProvider implements Provider {
  readonly name = "nvidia";
  private apiKey: string;
  private baseUrl = "https://integrate.api.nvidia.com/v1/chat/completions";

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  private ensureKey() {
    if (!this.apiKey) {
      throw new Error(
        "NVIDIA API key not set. Get a free key at build.nvidia.com, then add it to ~/.huntercode/config.json under apiKeys.nvidia",
      );
    }
  }

  // (a) tool DEFINITION: internal schema -> OpenAI function format.
  private formatTools(tools: ToolSchema[]) {
    return tools.map((t) => ({
      type: "function",
      function: {
        name: t.name,
        description: t.description,
        parameters: t.parameters,
      },
    }));
  }

  // (c) message/result formatting -> OpenAI chat messages.
  private formatMessages(messages: Message[]) {
    return messages.map((m) => {
      if (m.role === "tool") {
        return { role: "tool", tool_call_id: m.toolCallId, content: m.content };
      }
      if (m.role === "assistant" && m.toolCalls?.length) {
        return {
          role: "assistant",
          content: m.content || null,
          tool_calls: m.toolCalls.map((c) => ({
            id: c.id,
            type: "function",
            function: { name: c.name, arguments: JSON.stringify(c.arguments) },
          })),
        };
      }
      return { role: m.role, content: m.content };
    });
  }

  // (b) tool CALL parsing + reasoning extraction.
  private parse(data: any): ChatResponse {
    const msg = data?.choices?.[0]?.message ?? {};
    const toolCalls: ToolCall[] = (msg.tool_calls ?? []).map((c: any, i: number) => {
      let args: Record<string, unknown> = {};
      try {
        args = c.function?.arguments ? JSON.parse(c.function.arguments) : {};
      } catch {
        args = {};
      }
      return {
        id: c.id ?? `call_${Date.now()}_${i}`,
        name: c.function?.name ?? "",
        arguments: args,
      };
    });

    // Reasoning: prefer the explicit field, else split a leading <think> block
    // out of the content so the answer stays clean.
    let content: string = msg.content ?? "";
    let reasoning: string | undefined =
      typeof msg.reasoning_content === "string" ? msg.reasoning_content : undefined;
    if (!reasoning) {
      const m = content.match(/^\s*<think>([\s\S]*?)<\/think>\s*/);
      if (m) {
        reasoning = m[1].trim();
        content = content.slice(m[0].length);
      }
    }
    reasoning = reasoning?.trim() || undefined;

    return { content, toolCalls, reasoning, raw: data };
  }

  async chat(
    messages: Message[],
    tools: ToolSchema[],
    opts: ChatOptions,
  ): Promise<ChatResponse> {
    this.ensureKey();
    const res = await fetch(this.baseUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: opts.model,
        messages: this.formatMessages(messages),
        tools: tools.length ? this.formatTools(tools) : undefined,
        temperature: opts.temperature ?? 0.7,
      }),
      signal: opts.signal,
    });
    if (!res.ok) {
      throw new Error(`NVIDIA request failed (${res.status}): ${await res.text()}`);
    }
    return this.parse(await res.json());
  }

  async chatStream(
    messages: Message[],
    tools: ToolSchema[],
    opts: ChatOptions,
    onDelta: StreamHandler | StreamCallbacks,
  ): Promise<ChatResponse> {
    const cb = toStreamCallbacks(onDelta);
    return streamOpenAICompatible({
      url: this.baseUrl,
      headers: { Authorization: `Bearer ${this.apiKey}` },
      ensureKey: () => this.ensureKey(),
      body: {
        model: opts.model,
        messages: this.formatMessages(messages),
        tools: tools.length ? this.formatTools(tools) : undefined,
        temperature: opts.temperature ?? 0.7,
      },
      signal: opts.signal,
      cb,
      label: "NVIDIA",
      fallback: () => this.chat(messages, tools, opts),
    });
  }
}

/**
 * Shared streaming loop for OpenAI-compatible `/chat/completions` backends
 * (NVIDIA, OpenRouter). Emits text + reasoning deltas live, accumulates
 * tool-call fragments, and falls back to a buffered call on any failure.
 */
export async function streamOpenAICompatible(args: {
  url: string;
  headers: Record<string, string>;
  ensureKey: () => void;
  body: Record<string, unknown>;
  signal?: AbortSignal;
  cb: StreamCallbacks;
  label: string;
  fallback: () => Promise<ChatResponse>;
}): Promise<ChatResponse> {
  args.ensureKey();
  let res: Response;
  try {
    res = await fetch(args.url, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...args.headers },
      body: JSON.stringify({
        ...args.body,
        stream: true,
        stream_options: { include_usage: true },
      }),
      signal: args.signal,
    });
  } catch {
    return args.fallback();
  }
  if (!res.ok) {
    throw new Error(`${args.label} request failed (${res.status}): ${await res.text()}`);
  }
  if (!res.body) return args.fallback();

  let content = "";
  let reasoning = "";
  let reasoningStreamed = false;
  let inThink = false;
  const acc = new ToolCallAccumulator();
  let usage: ChatResponse["usage"];

  try {
    for await (const payload of sseLines(res.body)) {
      let json: any;
      try {
        json = JSON.parse(payload);
      } catch {
        continue;
      }
      if (json.usage) {
        usage = {
          promptTokens: json.usage.prompt_tokens,
          completionTokens: json.usage.completion_tokens,
        };
      }
      const choice = json.choices?.[0];
      const delta = choice?.delta;
      if (!delta) continue;

      // Explicit reasoning field (e.g. nemotron / gpt-oss).
      if (typeof delta.reasoning_content === "string" && delta.reasoning_content) {
        reasoning += delta.reasoning_content;
        reasoningStreamed = true;
        args.cb.onReasoning?.(delta.reasoning_content);
      }

      // Inline <think>…</think> reasoning split out of the text stream.
      let text: string = typeof delta.content === "string" ? delta.content : "";
      while (text) {
        if (inThink) {
          const end = text.indexOf("</think>");
          if (end === -1) {
            reasoning += text;
            reasoningStreamed = true;
            args.cb.onReasoning?.(text);
            text = "";
          } else {
            const seg = text.slice(0, end);
            if (seg) {
              reasoning += seg;
              reasoningStreamed = true;
              args.cb.onReasoning?.(seg);
            }
            text = text.slice(end + "</think>".length);
            inThink = false;
          }
        } else {
          const start = text.indexOf("<think>");
          if (start === -1) {
            content += text;
            args.cb.onText(text);
            text = "";
          } else {
            const seg = text.slice(0, start);
            if (seg) {
              content += seg;
              args.cb.onText(seg);
            }
            text = text.slice(start + "<think>".length);
            inThink = true;
          }
        }
      }

      if (delta.tool_calls) acc.add(delta);
    }
  } catch {
    // Stream broke mid-flight with nothing usable — fall back cleanly.
    if (!content && !acc.size) return args.fallback();
  }

  return {
    content,
    toolCalls: acc.finish() as ToolCall[],
    reasoning: reasoning.trim() || undefined,
    reasoningStreamed: reasoningStreamed || undefined,
    usage,
  };
}
