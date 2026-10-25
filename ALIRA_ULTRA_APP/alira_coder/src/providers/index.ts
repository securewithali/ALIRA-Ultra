import type { Config } from "../config.js";
import type { Provider } from "../types.js";
import { OllamaProvider } from "./ollama.js";
import { AnthropicProvider } from "./anthropic.js";
import { GeminiProvider } from "./gemini.js";
import { OpenRouterProvider } from "./openrouter.js";
import { NvidiaProvider } from "./nvidia.js";

/**
 * Build the active Provider from config. This is the only place that maps a
 * provider name to a concrete implementation — the agent loop stays unaware.
 */
export function getProvider(config: Config): Provider {
  switch (config.provider) {
    case "ollama":
      return new OllamaProvider(config.ollamaUrl);
    case "anthropic":
      return new AnthropicProvider(config.apiKeys.anthropic);
    case "gemini":
      return new GeminiProvider(config.apiKeys.gemini);
    case "openrouter":
      return new OpenRouterProvider(config.apiKeys.openrouter);
    case "nvidia":
      return new NvidiaProvider(config.apiKeys.nvidia);
    default:
      throw new Error(`Unknown provider: ${config.provider}`);
  }
}

export const PROVIDER_NAMES = ["ollama", "anthropic", "gemini", "openrouter", "nvidia"] as const;

/** The model selected automatically when switching to a provider. */
export const DEFAULT_MODELS: Record<(typeof PROVIDER_NAMES)[number], string> = {
  ollama: "qwen2.5-coder",
  anthropic: "claude-sonnet-4-6",
  gemini: "gemini-3.5-flash-lite",
  openrouter: "google/gemini-2.0-flash-exp:free",
  nvidia: "meta/llama-3.3-70b-instruct",
};

export interface ModelPreset {
  value: string;
  /** Has a usable free tier (informational only). */
  free?: boolean;
}

/**
 * Suggested models shown by `/model`. The user can type any model name; these
 * are just convenient starting points. For Ollama we prefer a live list of
 * installed models and fall back to these.
 */
export const MODEL_PRESETS: Record<(typeof PROVIDER_NAMES)[number], ModelPreset[]> = {
  ollama: [
    { value: "qwen2.5-coder", free: true },
    { value: "qwen2.5-coder:7b", free: true },
    { value: "qwen2.5-coder:3b", free: true },
    { value: "llama3.1:8b", free: true },
    { value: "deepseek-coder-v2", free: true },
  ],
  anthropic: [
    { value: "claude-sonnet-4-6" },
    { value: "claude-opus-4-8" },
    { value: "claude-haiku-4-5" },
  ],
  gemini: [
    { value: "gemini-3.5-flash-lite", free: true },
    { value: "gemini-flash-lite-latest", free: true },
    { value: "gemini-3.5-flash", free: true },
    { value: "gemini-3.8-flash", free: true },
    { value: "gemini-flash-latest", free: true },
  ],
  openrouter: [
    { value: "google/gemini-2.0-flash-exp:free", free: true },
    { value: "deepseek/deepseek-chat" },
    { value: "anthropic/claude-3.5-sonnet" },
    { value: "meta-llama/llama-3.3-70b-instruct" },
  ],
  // NVIDIA build platform — all have a usable free tier with a nvapi- key.
  // The nemotron-super and gpt-oss models expose a reasoning ("thinking") trace.
  nvidia: [
    { value: "meta/llama-3.3-70b-instruct", free: true },
    { value: "qwen/qwen3-next-80b-a3b-instruct", free: true },
    { value: "nvidia/llama-3.3-nemotron-super-49b-v1.5", free: true },
    { value: "openai/gpt-oss-120b", free: true },
    { value: "mistralai/codestral-22b-instruct-v0.1", free: true },
  ],
};
