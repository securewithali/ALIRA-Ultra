import type { Config } from "../config.js";
import { registerTool } from "../tools/index.js";
import type { JSONSchema } from "../types.js";
import { McpClient } from "./client.js";

/**
 * MCP integration: connect configured servers on startup, discover their tools,
 * and merge them into the agent's toolset. Tool names are namespaced as
 * `mcp_<server>_<tool>` to avoid collisions with built-ins and each other.
 * Connection failures are non-fatal — they warn and the rest keeps working.
 */

export interface McpServerStatus {
  name: string;
  connected: boolean;
  tools: string[];
  error?: string;
}

const clients: McpClient[] = [];
const status: McpServerStatus[] = [];

function sanitize(s: string): string {
  return s.replace(/[^a-zA-Z0-9_]/g, "_");
}

/**
 * Connect all enabled MCP servers from config. Returns a one-line summary, or
 * "" if none are configured. Safe to call once at startup.
 */
export async function connectMcpServers(config: Config): Promise<string> {
  const entries = Object.entries(config.mcpServers ?? {}).filter(
    ([, c]) => c && c.enabled !== false && c.command,
  );
  if (!entries.length) return "";

  await Promise.all(
    entries.map(async ([name, cfg]) => {
      const client = new McpClient(name, cfg);
      const st: McpServerStatus = { name, connected: false, tools: [] };
      status.push(st);
      try {
        await client.connect();
        clients.push(client);
        st.connected = true;
        for (const tool of client.tools) {
          const toolName = `mcp_${sanitize(name)}_${sanitize(tool.name)}`;
          st.tools.push(toolName);
          registerTool({
            schema: {
              name: toolName,
              description: `[MCP:${name}] ${tool.description ?? tool.name}`,
              parameters: normalizeSchema(tool.inputSchema),
            },
            execute: (args) => client.callTool(tool.name, args),
          });
        }
      } catch (e) {
        st.error = (e as Error).message;
        client.close();
      }
    }),
  );

  const ok = status.filter((s) => s.connected);
  const failed = status.filter((s) => !s.connected);
  const parts: string[] = [];
  if (ok.length) parts.push(`MCP: connected ${ok.map((s) => `${s.name} (${s.tools.length})`).join(", ")}`);
  if (failed.length) parts.push(`MCP: failed ${failed.map((s) => s.name).join(", ")}`);
  return parts.join(" · ");
}

/** Current MCP connection status, for the /mcp command. */
export function mcpStatus(): McpServerStatus[] {
  return status;
}

/** Disconnect all MCP servers (called on shutdown). */
export function closeMcpServers(): void {
  for (const c of clients) c.close();
}

/** Coerce an MCP inputSchema into our JSONSchema shape (object with properties). */
function normalizeSchema(schema: any): JSONSchema {
  if (schema && schema.type === "object" && schema.properties) {
    return {
      type: "object",
      properties: schema.properties,
      required: Array.isArray(schema.required) ? schema.required : undefined,
    };
  }
  return { type: "object", properties: {} };
}
