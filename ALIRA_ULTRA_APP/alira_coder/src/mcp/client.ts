import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import type { McpServerConfig } from "../config.js";

/**
 * A minimal MCP (Model Context Protocol) client over the stdio transport.
 *
 * Deliberately dependency-free: the MCP stdio transport is newline-delimited
 * JSON-RPC 2.0, which is small enough to speak by hand and keeps HunterCode
 * lightweight (no `@modelcontextprotocol/sdk`). We implement just what the agent
 * needs: `initialize`, `tools/list`, and `tools/call`.
 */

export interface McpTool {
  name: string;
  description?: string;
  inputSchema?: any;
}

interface Pending {
  resolve: (v: any) => void;
  reject: (e: Error) => void;
}

export class McpClient {
  readonly name: string;
  private proc: ChildProcessWithoutNullStreams | null = null;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private buffer = "";
  tools: McpTool[] = [];

  constructor(name: string, private cfg: McpServerConfig) {
    this.name = name;
  }

  /** Spawn the server, perform the initialize handshake, and list its tools. */
  async connect(timeoutMs = 15_000): Promise<void> {
    this.proc = spawn(this.cfg.command, this.cfg.args ?? [], {
      env: { ...process.env, ...(this.cfg.env ?? {}) },
      stdio: ["pipe", "pipe", "pipe"],
    });

    this.proc.on("error", (e) => this.failAll(e));
    this.proc.on("exit", () => this.failAll(new Error("MCP server exited")));
    this.proc.stdout.setEncoding("utf8");
    this.proc.stdout.on("data", (chunk: string) => this.onData(chunk));
    // Drain stderr so the pipe never blocks; ignore content.
    this.proc.stderr.on("data", () => {});

    await this.withTimeout(
      this.request("initialize", {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "huntercode", version: "1.0.0" },
      }),
      timeoutMs,
    );
    this.notify("notifications/initialized", {});

    const listed = await this.withTimeout(this.request("tools/list", {}), timeoutMs);
    this.tools = Array.isArray(listed?.tools) ? listed.tools : [];
  }

  /** Call a tool and return its textual result. */
  async callTool(name: string, args: Record<string, unknown>): Promise<string> {
    const res = await this.request("tools/call", { name, arguments: args });
    const parts: any[] = Array.isArray(res?.content) ? res.content : [];
    const text = parts
      .map((p) => (typeof p?.text === "string" ? p.text : p?.type ? `[${p.type}]` : ""))
      .filter(Boolean)
      .join("\n");
    if (res?.isError) return `Error from MCP tool ${name}: ${text || "unknown error"}`;
    return text || "(no output)";
  }

  close(): void {
    try {
      this.proc?.kill();
    } catch {
      /* ignore */
    }
    this.proc = null;
  }

  // ---- internals ----

  private onData(chunk: string): void {
    this.buffer += chunk;
    let nl: number;
    while ((nl = this.buffer.indexOf("\n")) !== -1) {
      const line = this.buffer.slice(0, nl).trim();
      this.buffer = this.buffer.slice(nl + 1);
      if (!line) continue;
      let msg: any;
      try {
        msg = JSON.parse(line);
      } catch {
        continue; // skip non-JSON log lines
      }
      if (typeof msg.id === "number" && this.pending.has(msg.id)) {
        const p = this.pending.get(msg.id)!;
        this.pending.delete(msg.id);
        if (msg.error) p.reject(new Error(msg.error.message ?? "MCP error"));
        else p.resolve(msg.result);
      }
    }
  }

  private send(obj: unknown): void {
    if (!this.proc) throw new Error("MCP server not connected");
    this.proc.stdin.write(JSON.stringify(obj) + "\n");
  }

  private request(method: string, params: unknown): Promise<any> {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      try {
        this.send({ jsonrpc: "2.0", id, method, params });
      } catch (e) {
        this.pending.delete(id);
        reject(e as Error);
      }
    });
  }

  private notify(method: string, params: unknown): void {
    this.send({ jsonrpc: "2.0", method, params });
  }

  private failAll(err: Error): void {
    for (const [, p] of this.pending) p.reject(err);
    this.pending.clear();
  }

  private withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      p,
      new Promise<T>((_, reject) =>
        setTimeout(() => reject(new Error(`MCP ${this.name} timed out`)), ms).unref(),
      ),
    ]);
  }
}
