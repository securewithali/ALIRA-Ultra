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
import { sseLines } from "./sse.js";

/**
 * Anthropic (Claude) provider.
 *
 * Implements the full Provider contract against the `/v1/messages` API. It is
 * key-guarded: with no API key configured it throws a clear, actionable error.
 * Token-level streaming is buffered (a single delta) — wiring up real SSE
 * streaming is a self-contained extension point in `chatStream`.
 *
 * Format notes (how Anthropic differs from the internal shape):
 *  - the system prompt is a top-level field, not a message;
 *  - tools use `input_schema` (not `parameters`);
 *  - tool calls are `tool_use` content blocks; results are `tool_result`
 *    blocks sent back inside a `user` message.
 */
export class AnthropicProvider implements Provider {
  readonly name = "anthropic";
  private apiKey: string;
  private baseUrl = "https://api.anthropic.com/v1/messages";
  private maxTokens = 4096;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  private ensureKey() {
    if (!this.apiKey) {
      throw new Error(
        "Anthropic API key not set. Add it to ~/.huntercode/config.json under apiKeys.anthropic",
      );
    }
  }

  // (a) tool DEFINITION: internal schema -> Anthropic tool format.
  private formatTools(tools: ToolSchema[]) {
    return tools.map((t) => ({
      name: t.name,
      description: t.description,
      input_schema: t.parameters,
    }));
  }

  // (c) message/result formatting. Extracts the system prompt and groups
  //     consecutive tool results into a single user turn (Anthropic disallows
  //     back-to-back user messages).
  private formatMessages(messages: Message[]): { system: string; messages: any[] } {
    let system = "";
    const out: any[] = [];

    for (const m of messages) {
      if (m.role === "system") {
        system += (system ? "\n\n" : "") + m.content;
        continue;
      }

      if (m.role === "tool") {
        const block = {
          type: "tool_result",
          tool_use_id: m.toolCallId,
          content: m.content,
        };
        const last = out[out.length - 1];
        if (last && last.role === "user" && Array.isArray(last.content)) {
          last.content.push(block);
        } else {
          out.push({ role: "user", content: [block] });
        }
        continue;
      }

      if (m.role === "assistant" && m.toolCalls?.length) {
        const content: any[] = [];
        if (m.content) content.push({ type: "text", text: m.content });
        for (const c of m.toolCalls) {
          content.push({ type: "tool_use", id: c.id, name: c.name, input: c.arguments });
        }
        out.push({ role: "assistant", content });
        continue;
      }

      out.push({ role: m.role, content: m.content });
    }

    return { system, messages: out };
  }

  // (b) tool CALL parsing: Anthropic content blocks -> normalized ToolCall[].
  private parse(data: any): ChatResponse {
    const blocks: any[] = Array.isArray(data?.content) ? data.content : [];
    let content = "";
    const toolCalls: ToolCall[] = [];
    for (const b of blocks) {
      if (b.type === "text") content += b.text ?? "";
      else if (b.type === "tool_use") {
        toolCalls.push({
          id: b.id,
          name: b.name,
          arguments: (b.input ?? {}) as Record<string, unknown>,
        });
      }
    }
    return { content, toolCalls, raw: data };
  }

  async chat(
    messages: Message[],
    tools: ToolSchema[],
    opts: ChatOptions,
  ): Promise<ChatResponse> {
    this.ensureKey();
    const { system, messages: msgs } = this.formatMessages(messages);
    const res = await fetch(this.baseUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": this.apiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: opts.model,
        max_tokens: this.maxTokens,
        temperature: opts.temperature ?? 0.7,
        system: system || undefined,
        messages: msgs,
        tools: tools.length ? this.formatTools(tools) : undefined,
      }),
      signal: opts.signal,
    });
    if (!res.ok) {
      throw new Error(`Anthropic request failed (${res.status}): ${await res.text()}`);
    }
    return this.parse(await res.json());
  }

  async chatStream(
    messages: Message[],
    tools: ToolSchema[],
    opts: ChatOptions,
    onDelta: StreamHandler | StreamCallbacks,
  ): Promise<ChatResponse> {
    this.ensureKey();
    const cb = toStreamCallbacks(onDelta);
    const { system, messages: msgs } = this.formatMessages(messages);

    let res: Response;
    try {
      res = await fetch(this.baseUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": this.apiKey,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: opts.model,
          max_tokens: this.maxTokens,
          temperature: opts.temperature ?? 0.7,
          system: system || undefined,
          messages: msgs,
          tools: tools.length ? this.formatTools(tools) : undefined,
          stream: true,
        }),
        signal: opts.signal,
      });
    } catch {
      return this.chat(messages, tools, opts);
    }
    if (!res.ok) {
      throw new Error(`Anthropic request failed (${res.status}): ${await res.text()}`);
    }
    if (!res.body) return this.chat(messages, tools, opts);

    let content = "";
    const blocks = new Map<number, { type: string; id?: string; name?: string; json: string }>();
    let usage: ChatResponse["usage"];

    try {
      for await (const payload of sseLines(res.body)) {
        let ev: any;
        try {
          ev = JSON.parse(payload);
        } catch {
          continue;
        }
        switch (ev.type) {
          case "message_start":
            if (ev.message?.usage)
              usage = { promptTokens: ev.message.usage.input_tokens };
            break;
          case "content_block_start": {
            const b = ev.content_block ?? {};
            blocks.set(ev.index, { type: b.type, id: b.id, name: b.name, json: "" });
            break;
          }
          case "content_block_delta": {
            const d = ev.delta ?? {};
            if (d.type === "text_delta" && d.text) {
              content += d.text;
              cb.onText(d.text);
            } else if (d.type === "input_json_delta") {
              const blk = blocks.get(ev.index);
              if (blk) blk.json += d.partial_json ?? "";
            }
            break;
          }
          case "message_delta":
            if (ev.usage?.output_tokens !== undefined)
              usage = { ...(usage ?? {}), completionTokens: ev.usage.output_tokens };
            break;
        }
      }
    } catch {
      if (!content && !blocks.size) return this.chat(messages, tools, opts);
    }

    const toolCalls: ToolCall[] = [];
    for (const [, b] of [...blocks.entries()].sort((a, c) => a[0] - c[0])) {
      if (b.type !== "tool_use") continue;
      let args: Record<string, unknown> = {};
      try {
        args = b.json ? JSON.parse(b.json) : {};
      } catch {
        args = {};
      }
      toolCalls.push({ id: b.id ?? `call_${Date.now()}`, name: b.name ?? "", arguments: args });
    }

    return { content, toolCalls, usage };
  }
}
