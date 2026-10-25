/**
 * `huntercode serve` — minimal HTTP API for headless callers (e.g. Maya).
 *
 * Implements the subset of OpenCode's server API that an orchestrator needs, so
 * an existing OpenCode HTTP client can talk to HunterCode with only a base-URL
 * change:
 *   GET  /global/health          -> { healthy: true }
 *   GET  /path                   -> { directory }
 *   POST /session                -> { id }
 *   GET  /session/:id            -> 200 if known
 *   POST /session/:id/message    -> { parts:[{type:'text',text}], info:{} }
 *   POST /session/:id/init       -> 200 (no-op)
 *   GET  /session/:id/diff       -> [ "<changed path>", ... ]
 *
 * One server instance is bound to one project directory (`--dir`), matching
 * OpenCode's per-cwd model; `/path` reports it so callers can verify cwd.
 */
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { randomUUID } from "node:crypto";
import { readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { loadConfig, loadDotEnv, applyEnvOverrides, type Config, type ProviderName } from "./config.js";
import { getProvider, PROVIDER_NAMES } from "./providers/index.js";
import { Session, type AgentUI } from "./agent.js";
import { IGNORED_DIRS } from "./tools/ignore.js";
import { bufferProgressSink, withProgress, type ProgressEvent } from "./progress.js";

interface ServeArgs {
  port: number;
  dir: string;
  provider?: string;
  model?: string;
}

function parseArgs(argv: string[]): ServeArgs {
  const out: ServeArgs = { port: 4096, dir: process.cwd() };
  for (let i = 0; i < argv.length; i++) {
    const next = () => argv[++i] ?? "";
    switch (argv[i]) {
      case "--port": out.port = Number(next()) || out.port; break;
      case "--dir": out.dir = next(); break;
      case "--provider": out.provider = next(); break;
      case "--model": out.model = next(); break;
    }
  }
  return out;
}

/** Snapshot file -> mtimeMs under `root`, skipping ignored/heavy dirs. */
function scanMtimes(root: string): Map<string, number> {
  const out = new Map<string, number>();
  const walk = (dir: string, depth: number) => {
    if (depth > 8) return;
    let entries: string[];
    try { entries = readdirSync(dir); } catch { return; }
    for (const name of entries) {
      if (IGNORED_DIRS.has(name)) continue;
      const full = join(dir, name);
      let st;
      try { st = statSync(full); } catch { continue; }
      if (st.isDirectory()) walk(full, depth + 1);
      else out.set(full, st.mtimeMs);
    }
  };
  walk(root, 0);
  return out;
}

/** Paths in `after` that are new or newer than in `before`. */
function diffMtimes(before: Map<string, number>, after: Map<string, number>): string[] {
  const changed: string[] = [];
  for (const [path, mtime] of after) {
    const prev = before.get(path);
    if (prev === undefined || mtime > prev) changed.push(path);
  }
  return changed;
}

const QUIET_UI: AgentUI = {
  onText: () => {},
  onReasoning: () => {},
  onToolCall: (label) => console.log(`[huntercode] ${label}`),
  print: () => {},
  confirm: async () => true,
  setStatus: () => {},
};

function send(res: ServerResponse, status: number, body: unknown): void {
  const json = JSON.stringify(body);
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(json);
}

function readBody(req: IncomingMessage): Promise<any> {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => {
      if (!data) return resolve({});
      try { resolve(JSON.parse(data)); } catch { resolve({}); }
    });
  });
}

/**
 * OpenCode-style model object {providerID, modelID} -> our provider/model.
 *
 * Defensive: a per-message override only applies when `providerID` names a
 * KNOWN provider. An unknown provider (e.g. a stale "opencode" from another
 * tool) is ignored entirely — model and all — so the server falls back to its
 * own global config instead of building an invalid provider and crashing.
 */
function modelToConfig(base: Config, model: any): Config {
  if (!model || typeof model !== "object") return base;
  const providerID = String(model.providerID || "").trim();
  const modelID = String(model.modelID || "").trim();
  // No provider given: accept a bare model override against the global provider.
  if (!providerID) return modelID ? { ...base, model: modelID } : base;
  // Provider given but unknown: ignore the whole override (use global config).
  if (!PROVIDER_NAMES.includes(providerID as ProviderName)) return base;
  const out: Config = { ...base, provider: providerID as ProviderName };
  if (modelID) out.model = modelID;
  return out;
}

interface SessionEntry {
  session: Session;
  changed: Set<string>;
  /** Progress events for the in-flight (or most recent) message turn. */
  progress: ProgressEvent[];
}

export async function serveMain(argv: string[]): Promise<void> {
  const args = parseArgs(argv);
  loadDotEnv(args.dir);
  let baseConfig: Config = applyEnvOverrides(loadConfig());
  if (args.provider) baseConfig = { ...baseConfig, provider: args.provider as ProviderName };
  if (args.model) baseConfig = { ...baseConfig, model: args.model };

  const rootDir = args.dir;
  const sessions = new Map<string, SessionEntry>();

  const server = createServer(async (req, res) => {
    const url = (req.url || "").split("?")[0];
    const method = req.method || "GET";

    try {
      if (method === "GET" && url === "/global/health") return send(res, 200, { healthy: true });
      if (method === "GET" && url === "/path") return send(res, 200, { directory: rootDir });

      if (method === "POST" && url === "/session") {
        const id = randomUUID();
        const cfg = baseConfig;
        sessions.set(id, { session: new Session(getProvider(cfg), cfg, rootDir), changed: new Set(), progress: [] });
        return send(res, 200, { id });
      }

      const sessionMatch = url.match(/^\/session\/([^/]+)(\/(message|init|diff|progress))?$/);
      if (sessionMatch) {
        const id = sessionMatch[1];
        const sub = sessionMatch[3];
        const entry = sessions.get(id);

        if (method === "GET" && !sub) {
          return entry ? send(res, 200, { id }) : send(res, 404, { error: "no such session" });
        }
        if (!entry) return send(res, 404, { error: "no such session" });

        if (method === "POST" && sub === "init") return send(res, 200, { ok: true });

        if (method === "GET" && sub === "diff") {
          return send(res, 200, [...entry.changed].map((p) => relative(rootDir, p) || p));
        }

        // Live progress for the in-flight/most-recent message. Poll with
        // ?since=<n> (the count already consumed) to get only new events.
        if (method === "GET" && sub === "progress") {
          const q = (req.url || "").split("?")[1] || "";
          const since = Number(new URLSearchParams(q).get("since") || "0") || 0;
          const events = since > 0 ? entry.progress.slice(since) : entry.progress;
          return send(res, 200, { events, next: entry.progress.length });
        }

        if (method === "POST" && sub === "message") {
          const body = await readBody(req);
          const parts = Array.isArray(body.parts) ? body.parts : [];
          const text = parts
            .filter((p: any) => p && p.type === "text" && p.text)
            .map((p: any) => String(p.text))
            .join("\n")
            .trim();
          if (!text) return send(res, 400, { error: "empty message" });

          // Per-message model override (providerID/modelID).
          const cfg = modelToConfig(baseConfig, body.model);
          const provider = getProvider(cfg);
          entry.session.setProvider(provider, cfg);

          const prompt = body.system ? `${String(body.system)}\n\n${text}` : text;

          // Fresh progress buffer for this turn; Maya can poll GET …/progress.
          entry.progress.length = 0;
          const sink = bufferProgressSink(entry.progress);
          const progressUI = withProgress(QUIET_UI, sink);
          sink.emit("started", { model: cfg.model, provider: cfg.provider });

          const before = scanMtimes(rootDir);
          let summary: string;
          try {
            summary = await entry.session.runTurn(prompt, progressUI);
          } catch (e) {
            sink.emit("error", { message: (e as Error).message });
            throw e;
          }
          const after = scanMtimes(rootDir);
          const changed = diffMtimes(before, after);
          for (const p of changed) entry.changed.add(p);
          sink.emit("done", { summary: summary || "Task complete." });

          return send(res, 200, {
            parts: [{ type: "text", text: summary || "Task complete." }],
            info: { changedFiles: changed.map((p) => relative(rootDir, p) || p) },
          });
        }
      }

      send(res, 404, { error: "not found" });
    } catch (e) {
      send(res, 500, { error: (e as Error).message });
    }
  });

  server.listen(args.port, "127.0.0.1", () => {
    console.log(
      `huntercode serve · http://127.0.0.1:${args.port} · ${baseConfig.provider} · ${baseConfig.model} · ${rootDir}`,
    );
  });
}
