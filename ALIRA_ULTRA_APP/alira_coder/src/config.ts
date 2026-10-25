import { homedir } from "node:os";
import { join } from "node:path";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from "node:fs";

import type { Mode } from "./modes.js";

export type ProviderName = "ollama" | "anthropic" | "gemini" | "openrouter" | "nvidia";

/** Runtime list of valid provider names (kept here to avoid an import cycle). */
const KNOWN_PROVIDERS: ProviderName[] = ["ollama", "anthropic", "gemini", "openrouter", "nvidia"];

/** One configured MCP server (stdio transport). */
export interface McpServerConfig {
  command: string;
  args?: string[];
  env?: Record<string, string>;
  /** Set false to keep it in config but not connect. */
  enabled?: boolean;
}

export interface Config {
  provider: ProviderName;
  model: string;
  ollamaUrl: string;
  apiKeys: {
    anthropic: string;
    gemini: string;
    openrouter: string;
    nvidia: string;
  };
  temperature: number;
  /** Default operating mode at startup. */
  mode: Mode;
  /** Whether file edits are applied automatically or after a y/n/a prompt. */
  editApproval: "auto" | "manual";
  /** Whether the agent may switch modes on its own ("auto") or must ask ("manual"). */
  autoMode: "auto" | "manual";
  /** Fraction of the model's context window at which to auto-compact (0–1). */
  compactThreshold: number;
  /** Sub-agent dispatch settings (off by default; flaky on weak models). */
  subagents: {
    enabled: boolean;
    maxPerTurn: number;
  };
  /** MCP servers to connect on startup, keyed by a display name. */
  mcpServers: Record<string, McpServerConfig>;
}

export const DEFAULT_CONFIG: Config = {
  provider: "ollama",
  model: "qwen2.5-coder",
  ollamaUrl: "http://localhost:11434",
  apiKeys: {
    anthropic: "",
    gemini: "",
    openrouter: "",
    nvidia: "",
  },
  temperature: 0.7,
  mode: "agent",
  editApproval: "manual",
  autoMode: "manual",
  compactThreshold: 0.75,
  subagents: { enabled: false, maxPerTurn: 3 },
  mcpServers: {},
};

export const CONFIG_DIR = join(homedir(), ".ALIRA-coder");
export const CONFIG_PATH = join(CONFIG_DIR, "config.json");

/** Provider -> env var that supplies its API key (for headless run/serve). */
const KEY_ENV: Record<keyof Config["apiKeys"], string> = {
  anthropic: "ANTHROPIC_API_KEY",
  gemini: "GEMINI_API_KEY",
  openrouter: "OPENROUTER_API_KEY",
  nvidia: "NVIDIA_API_KEY",
};

/**
 * Load `.env` from `dir` into `process.env` (only keys not already set).
 * Minimal `KEY=VALUE` parser — no dependency. Quietly does nothing if absent.
 */
export function loadDotEnv(dir: string = process.cwd()): void {
  const path = join(dir, ".env");
  if (!existsSync(path)) return;
  try {
    for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/);
      if (!m) continue;
      const k = m[1];
      let v = m[2].trim();
      if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
        v = v.slice(1, -1);
      }
      if (process.env[k] === undefined) process.env[k] = v;
    }
  } catch {
    // ignore malformed .env
  }
}

/**
 * Overlay environment vTABBUbles onto a config. Lets Maya (or any caller) drive
 * HunterCode headlessly without writing `~/.huntercode/config.json`.
 * Precedence handled by callers: explicit flag > env > config.json > defaults.
 */
export function applyEnvOverrides(config: Config): Config {
  const out: Config = { ...config, apiKeys: { ...config.apiKeys } };
  // Provider override only takes effect when it names a known provider. An
  // unknown provider (e.g. a stale "opencode" left over from another tool) is
  // ignored entirely — along with any model override that came with it — so we
  // fall back to the global ~/.huntercode/config.json instead of crashing.
  const provider = (process.env.HUNTERCODE_PROVIDER || "").trim();
  const providerValid = !provider || KNOWN_PROVIDERS.includes(provider as ProviderName);
  if (provider && providerValid) out.provider = provider as ProviderName;
  const model = (process.env.HUNTERCODE_MODEL || "").trim();
  if (model && providerValid) out.model = model;
  const ollamaUrl = (process.env.HUNTERCODE_OLLAMA_URL || "").trim();
  if (ollamaUrl) out.ollamaUrl = ollamaUrl;
  const temp = (process.env.HUNTERCODE_TEMPERATURE || "").trim();
  if (temp && !Number.isNaN(Number(temp))) out.temperature = Number(temp);
  const editApproval = (process.env.HUNTERCODE_EDIT_APPROVAL || "").trim();
  if (editApproval === "auto" || editApproval === "manual") out.editApproval = editApproval;
  const autoMode = (process.env.HUNTERCODE_AUTO_MODE || "").trim();
  if (autoMode === "auto" || autoMode === "manual") out.autoMode = autoMode;
  for (const [prov, envName] of Object.entries(KEY_ENV) as [keyof Config["apiKeys"], string][]) {
    const v = (process.env[envName] || "").trim();
    if (v) out.apiKeys[prov] = v;
  }
  return out;
}

/**
 * Load config from ~/.huntercode/config.json, creating it with defaults on
 * first run. Unknown/missing fields are merged with defaults so older config
 * files keep working as the schema grows.
 */
export function loadConfig(): Config {
  if (!existsSync(CONFIG_PATH)) {
    saveConfig(DEFAULT_CONFIG);
    return { ...DEFAULT_CONFIG };
  }
  try {
    const raw = JSON.parse(readFileSync(CONFIG_PATH, "utf8"));
    return {
      ...DEFAULT_CONFIG,
      ...raw,
      apiKeys: { ...DEFAULT_CONFIG.apiKeys, ...(raw.apiKeys ?? {}) },
      subagents: { ...DEFAULT_CONFIG.subagents, ...(raw.subagents ?? {}) },
      mcpServers: { ...DEFAULT_CONFIG.mcpServers, ...(raw.mcpServers ?? {}) },
    };
  } catch {
    // Corrupt config — fall back to defaults rather than crashing.
    return { ...DEFAULT_CONFIG };
  }
}

export function saveConfig(config: Config): void {
  if (!existsSync(CONFIG_DIR)) {
    mkdirSync(CONFIG_DIR, { recursive: true });
  }
  writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2) + "\n", "utf8");
}
