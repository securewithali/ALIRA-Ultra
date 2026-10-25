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

/**
 * Ollama provider — talks to a local Ollama server via its native
 * `/api/chat` tool-calling API. This is the reference implementation of the
 * Provider contract; the cloud providers mirror its structure.
 *
 * Ollama uses an OpenAI-flavored tool format and returns tool-call arguments
 * as already-parsed objects (not JSON strings).
 */
export class OllamaProvider implements Provider {
  readonly name = "ollama";
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  /** List locally installed models via Ollama's /api/tags endpoint. */
  async listModels(): Promise<string[]> {
    const res = await fetch(`${this.baseUrl}/api/tags`);
    if (!res.ok) {
      throw new Error(`Ollama /api/tags failed (${res.status})`);
    }
    const data: any = await res.json();
    return (data?.models ?? []).map((m: any) => m.name).filter(Boolean);
  }

  // (a) tool DEFINITION: internal schema -> Ollama/OpenAI function format.
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

  // (c) tool RESULT / history formatting: internal messages -> Ollama messages.
  private formatMessages(messages: Message[]) {
    return messages.map((m) => {
      if (m.role === "tool") {
        return { role: "tool", content: m.content, name: m.name };
      }
      if (m.role === "assistant" && m.toolCalls?.length) {
        return {
          role: "assistant",
          content: m.content,
          tool_calls: m.toolCalls.map((c) => ({
            function: { name: c.name, arguments: c.arguments },
          })),
        };
      }
      return { role: m.role, content: m.content };
    });
  }

  // (b) tool CALL parsing: Ollama message -> normalized ToolCall[].
  private parseToolCalls(message: any): ToolCall[] {
    const raw = message?.tool_calls;
    if (!Array.isArray(raw)) return [];
    return raw.map((c: any, i: number) => {
      let args = c?.function?.arguments ?? {};
      if (typeof args === "string") {
        try {
          args = JSON.parse(args);
        } catch {
          args = {};
        }
      }
      return {
        id: c?.id ?? `call_${Date.now()}_${i}`,
        name: c?.function?.name ?? "",
        arguments: args as Record<string, unknown>,
      };
    });
  }

  private body(messages: Message[], tools: ToolSchema[], opts: ChatOptions, stream: boolean) {
    return {
      model: opts.model,
      messages: this.formatMessages(messages),
      tools: tools.length ? this.formatTools(tools) : undefined,
      stream,
      options: { temperature: opts.temperature ?? 0.7 },
    };
  }

  async chat(
    messages: Message[],
    tools: ToolSchema[],
    opts: ChatOptions,
  ): Promise<ChatResponse> {
    const res = await fetch(`${this.baseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(this.body(messages, tools, opts, false)),
      signal: opts.signal,
    });
    if (!res.ok) {
      throw new Error(`Ollama request failed (${res.status}): ${await res.text()}`);
    }
    const data: any = await res.json();
    return {
      content: data?.message?.content ?? "",
      toolCalls: this.parseToolCalls(data?.message),
      raw: data,
    };
  }

  async chatStream(
    messages: Message[],
    tools: ToolSchema[],
    opts: ChatOptions,
    onDelta: StreamHandler | StreamCallbacks,
  ): Promise<ChatResponse> {
    const cb = toStreamCallbacks(onDelta);
    const res = await fetch(`${this.baseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(this.body(messages, tools, opts, true)),
      signal: opts.signal,
    });
    if (!res.ok) {
      throw new Error(`Ollama request failed (${res.status}): ${await res.text()}`);
    }
    if (!res.body) {
      // No stream body — fall back to a single response parse.
      return this.chat(messages, tools, opts);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let content = "";
    // Tool calls arrive in their own (usually final) chunk; capture them
    // separately so plain content chunks don't clobber them.
    let toolCallSource: any = null;

    // Ollama streams newline-delimited JSON objects.
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        let chunk: any;
        try {
          chunk = JSON.parse(trimmed);
        } catch {
          continue;
        }
        const delta = chunk?.message?.content ?? "";
        if (delta) {
          content += delta;
          cb.onText(delta);
        }
        if (chunk?.message?.tool_calls?.length) {
          toolCallSource = chunk.message;
        }
      }
    }

    return {
      content,
      toolCalls: this.parseToolCalls(toolCallSource),
      raw: toolCallSource,
    };
  }
}
