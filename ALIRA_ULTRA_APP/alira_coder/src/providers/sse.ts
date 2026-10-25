/**
 * Shared Server-Sent-Events plumbing for the streaming providers.
 *
 * All of HunterCode's cloud backends stream over SSE (`data: {json}\n\n`), so
 * this factors the read-loop + line-framing into one place. Each provider then
 * only has to interpret the decoded JSON payloads in its own wire format.
 */

/**
 * Async generator over an SSE response body. Yields the raw payload string of
 * each `data:` line (with the `data: ` prefix stripped). The `[DONE]` sentinel
 * used by OpenAI-style APIs is filtered out automatically.
 *
 * Robust to chunk boundaries splitting a line, and to multi-line events.
 */
export async function* sseLines(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Events are separated by blank lines; lines within share a `data:` key.
      let nl: number;
      while ((nl = buffer.indexOf("\n")) !== -1) {
        const line = buffer.slice(0, nl).replace(/\r$/, "");
        buffer = buffer.slice(nl + 1);
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload || payload === "[DONE]") continue;
        yield payload;
      }
    }
    // Flush a trailing data line with no terminating newline.
    const tail = buffer.trim();
    if (tail.startsWith("data:")) {
      const payload = tail.slice(5).trim();
      if (payload && payload !== "[DONE]") yield payload;
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      /* already released */
    }
  }
}

/**
 * Accumulates OpenAI-style streamed `tool_calls` deltas (keyed by array index)
 * into complete `{id, name, arguments}` records. Arguments arrive as a JSON
 * string split across many chunks, so we concatenate then parse at the end.
 */
export class ToolCallAccumulator {
  private byIndex = new Map<
    number,
    { id?: string; name?: string; args: string }
  >();

  add(delta: any): void {
    const calls = delta?.tool_calls;
    if (!Array.isArray(calls)) return;
    for (const c of calls) {
      const idx = typeof c.index === "number" ? c.index : this.byIndex.size;
      const cur = this.byIndex.get(idx) ?? { args: "" };
      if (c.id) cur.id = c.id;
      if (c.function?.name) cur.name = c.function.name;
      if (typeof c.function?.arguments === "string") cur.args += c.function.arguments;
      this.byIndex.set(idx, cur);
    }
  }

  /** Resolve to normalized ToolCall[]; parses each argument JSON blob safely. */
  finish(): { id: string; name: string; arguments: Record<string, unknown> }[] {
    const out: { id: string; name: string; arguments: Record<string, unknown> }[] = [];
    let i = 0;
    for (const [, c] of [...this.byIndex.entries()].sort((a, b) => a[0] - b[0])) {
      let args: Record<string, unknown> = {};
      try {
        args = c.args ? JSON.parse(c.args) : {};
      } catch {
        args = {};
      }
      out.push({ id: c.id ?? `call_${Date.now()}_${i++}`, name: c.name ?? "", arguments: args });
    }
    return out;
  }

  get size(): number {
    return this.byIndex.size;
  }
}
