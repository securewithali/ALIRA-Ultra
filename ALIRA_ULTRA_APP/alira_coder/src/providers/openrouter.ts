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
import { streamOpenAICompatible } from "./nvidia.js";

/**
 * OpenRouter provider.
 *
 * OpenRouter exposes an OpenAI-compatible `/chat/completions` API, so this
 * doubles as the reference for any OpenAI-style backend. Key-guarded;
 * streaming is buffered (see Anthropic note).
 *
 * Format notes:
 *  - tools use the `{type:'function', function:{...}}` envelope;
 *  - tool-call arguments come back as a JSON *string* that must be parsed;
 *  - tool results are `{role:'tool', tool_call_id, content}` messages.
 */
export class OpenRouterProvider implements Provider {
  readonly name = "openrouter";
  private apiKey: string;
  private baseUrl = "https://openrouter.ai/api/v1/chat/completions";

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  private ensureKey() {
    if (!this.apiKey) {
      throw new Error(
        "OpenRouter API key not set. Add it to ~/.huntercode/config.json under apiKeys.openrouter",
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

  // (b) tool CALL parsing: OpenAI tool_calls (string args) -> ToolCall[].
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
    return { content: msg.content ?? "", toolCalls, raw: data };
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
        "HTTP-Referer": "https://github.com/HunterisLive-1/HunterCode",
        "X-Title": "HunterCode",
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
      throw new Error(`OpenRouter request failed (${res.status}): ${await res.text()}`);
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
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "HTTP-Referer": "https://github.com/HunterisLive-1/HunterCode",
        "X-Title": "HunterCode",
      },
      ensureKey: () => this.ensureKey(),
      body: {
        model: opts.model,
        messages: this.formatMessages(messages),
        tools: tools.length ? this.formatTools(tools) : undefined,
        temperature: opts.temperature ?? 0.7,
      },
      signal: opts.signal,
      cb,
      label: "OpenRouter",
      fallback: () => this.chat(messages, tools, opts),
    });
  }
}
