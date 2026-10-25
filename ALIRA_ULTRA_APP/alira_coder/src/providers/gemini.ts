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
 * Google Gemini provider.
 *
 * Implements the Provider contract against the `generateContent` REST API.
 * Key-guarded; streaming is buffered (see Anthropic note).
 *
 * Format notes:
 *  - roles are `user` / `model` (no `assistant`); the system prompt goes in
 *    `system_instruction`;
 *  - tools are `functionDeclarations`;
 *  - tool calls are `functionCall` parts; results are `functionResponse` parts.
 */
export class GeminiProvider implements Provider {
  readonly name = "gemini";
  private apiKey: string;
  private base = "https://generativelanguage.googleapis.com/v1beta/models";

  constructor(apiKey: string) {
    this.apiKey = apiKey;
  }

  private ensureKey() {
    if (!this.apiKey) {
      throw new Error(
        "Gemini API key not set. Add it to ~/.ALIRA-coder/config.json under apiKeys.gemini\n" +
        "Run: python setup_ALIRA_coder.py to configure automatically",
      );
    }
  }

  // (a) tool DEFINITION: internal schema -> Gemini functionDeclarations.
  private formatTools(tools: ToolSchema[]) {
    if (!tools.length) return undefined;
    return [
      {
        functionDeclarations: tools.map((t) => ({
          name: t.name,
          description: t.description,
          parameters: t.parameters,
        })),
      },
    ];
  }

  /** thoughtSignature per tool-call id (Gemini 3.x needs them echoed back). */
  private sigs = new Map<string, string>();

  // (c) message/result formatting -> Gemini `contents` + system_instruction.
  private formatMessages(messages: Message[]): {
    systemInstruction?: any;
    contents: any[];
  } {
    let system = "";
    const contents: any[] = [];

    for (const m of messages) {
      if (m.role === "system") {
        system += (system ? "\n\n" : "") + m.content;
        continue;
      }
      if (m.role === "tool") {
        // Gemini 3.x rejects role "function" — tool results go in a "user" turn, and
        // parallel tool results must share ONE turn (parts == number of calls).
        const part = { functionResponse: { name: m.name, response: { result: m.content } } };
        const last = contents[contents.length - 1];
        if (last && last.role === "user" && last.parts.every((p: any) => p.functionResponse)) {
          last.parts.push(part);
        } else {
          contents.push({ role: "user", parts: [part] });
        }
        continue;
      }
      if (m.role === "assistant") {
        const parts: any[] = [];
        if (m.content) parts.push({ text: m.content });
        for (const c of m.toolCalls ?? []) {
          const sig = this.sigs.get(c.id);
          parts.push({ functionCall: { name: c.name, args: c.arguments }, ...(sig ? { thoughtSignature: sig } : {}) });
        }
        contents.push({ role: "model", parts });
        continue;
      }
      // user
      contents.push({ role: "user", parts: [{ text: m.content }] });
    }

    return {
      systemInstruction: system ? { parts: [{ text: system }] } : undefined,
      contents,
    };
  }

  // (b) tool CALL parsing: Gemini parts -> normalized ToolCall[].
  private parse(data: any): ChatResponse {
    const parts: any[] = data?.candidates?.[0]?.content?.parts ?? [];
    let content = "";
    const toolCalls: ToolCall[] = [];
    let i = 0;
    for (const p of parts) {
      if (typeof p.text === "string") content += p.text;
      else if (p.functionCall) {
        const id = `call_${Date.now()}_${i++}`;
        if (p.thoughtSignature) this.sigs.set(id, p.thoughtSignature);
        toolCalls.push({
          id,
          name: p.functionCall.name,
          arguments: (p.functionCall.args ?? {}) as Record<string, unknown>,
        });
      }
    }
    return { content, toolCalls, raw: data };
  }

  /** Models to fall back to when the requested one is out of quota / retired / overloaded. */
  private static FALLBACKS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
  ];
  /** Models that returned 429/404 in this process — skipped from then on. */
  private bad = new Set<string>();

  private candidates(model: string): string[] {
    const all = [model, ...GeminiProvider.FALLBACKS.filter((m) => m !== model)];
    const ok = all.filter((m) => !this.bad.has(m));
    return ok.length ? ok : all;
  }

  /**
   * POST to Gemini with automatic model fallback: 429 (free-tier quota) and 404
   * (model retired / not available to new keys) move on to the next model; 503
   * (overloaded) is retried once first. Other statuses (400/401/403) are real
   * errors and are thrown immediately.
   */
  private async post(
    kind: "generateContent" | "streamGenerateContent",
    body: string,
    opts: ChatOptions,
  ): Promise<Response> {
    let status = 0;
    let text = "";
    for (const model of this.candidates(opts.model)) {
      for (let attempt = 0; attempt < 2; attempt++) {
        const q = kind === "streamGenerateContent" ? "?alt=sse&" : "?";
        const url = `${this.base}/${model}:${kind}${q}key=${this.apiKey}`;
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
          signal: opts.signal,
        });
        if (res.ok) {
          if (model !== opts.model) process.stderr.write(`[gemini] using fallback model ${model}
`);
          return res;
        }
        status = res.status;
        text = await res.text();
        if (status === 503 && attempt === 0) {
          await new Promise((r) => setTimeout(r, 1500));
          continue;
        }
        if (status === 429 || status === 404) this.bad.add(model);
        break;
      }
      if (![429, 404, 503, 500].includes(status)) break;
    }
    throw new Error(`Gemini request failed (${status}): ${text}`);
  }

  async chat(
    messages: Message[],
    tools: ToolSchema[],
    opts: ChatOptions,
  ): Promise<ChatResponse> {
    this.ensureKey();
    const { systemInstruction, contents } = this.formatMessages(messages);
    const res = await this.post(
      "generateContent",
      JSON.stringify({
        contents,
        systemInstruction,
        tools: this.formatTools(tools),
        generationConfig: { temperature: opts.temperature ?? 0.7 },
      }),
      opts,
    );
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
    const { systemInstruction, contents } = this.formatMessages(messages);
    let res: Response;
    try {
      res = await this.post(
        "streamGenerateContent",
        JSON.stringify({
          contents,
          systemInstruction,
          tools: this.formatTools(tools),
          generationConfig: { temperature: opts.temperature ?? 0.7 },
        }),
        opts,
      );
    } catch (e) {
      if (/Gemini request failed/.test((e as Error).message)) throw e; // real API error
      return this.chat(messages, tools, opts); // network error -> non-stream retry
    }
    if (!res.body) return this.chat(messages, tools, opts);

    let content = "";
    const toolCalls: ToolCall[] = [];
    let usage: ChatResponse["usage"];
    let i = 0;

    try {
      for await (const payload of sseLines(res.body)) {
        let chunk: any;
        try {
          chunk = JSON.parse(payload);
        } catch {
          continue;
        }
        if (chunk.usageMetadata) {
          usage = {
            promptTokens: chunk.usageMetadata.promptTokenCount,
            completionTokens: chunk.usageMetadata.candidatesTokenCount,
          };
        }
        const parts: any[] = chunk?.candidates?.[0]?.content?.parts ?? [];
        for (const p of parts) {
          if (typeof p.text === "string" && p.text) {
            content += p.text;
            cb.onText(p.text);
          } else if (p.functionCall) {
            const id = `call_${Date.now()}_${i++}`;
            if (p.thoughtSignature) this.sigs.set(id, p.thoughtSignature);
            toolCalls.push({
              id,
              name: p.functionCall.name,
              arguments: (p.functionCall.args ?? {}) as Record<string, unknown>,
            });
          }
        }
      }
    } catch {
      if (!content && !toolCalls.length) return this.chat(messages, tools, opts);
    }

    return { content, toolCalls, usage };
  }
}
