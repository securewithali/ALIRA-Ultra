/**
 * Single source of truth for slash commands and the pure logic that powers
 * autocomplete. This file has NO terminal I/O so it can be unit-tested directly.
 */
import { MODES } from "./modes.js";
import { PROVIDER_NAMES, MODEL_PRESETS } from "./providers/index.js";
import type { ProviderName } from "./config.js";

/** A command shown in `/help` and the autocomplete menu. */
export interface Command {
  name: string;
  description: string;
  /** Whether the command takes an argument (so we append a space on accept). */
  takesArg?: boolean;
}

/** One row in the autocomplete dropdown. */
export interface Suggestion {
  /** The text to insert (a command name, or an argument value). */
  value: string;
  /** Short description shown dimmed beside the value (commands only). */
  description?: string;
  /** True when this is a command name (vs an argument value). */
  isCommand: boolean;
}

/** The commands offered in the menu. `quit` stays a handled alias but is hidden. */
export const COMMANDS: Command[] = [
  { name: "help", description: "Show available commands" },
  { name: "clear", description: "Reset the conversation history" },
  { name: "mode", description: "Switch mode (agent, plan, ask)", takesArg: true },
  { name: "model", description: "Show, list, or switch the model", takesArg: true },
  { name: "provider", description: "Switch the provider", takesArg: true },
  { name: "apikey", description: "Set a provider's API key", takesArg: true },
  { name: "editapproval", description: "Edit approval: auto or manual", takesArg: true },
  { name: "automode", description: "Agent mode-switching: auto or manual", takesArg: true },
  { name: "compact", description: "Summarize & shrink the conversation context" },
  { name: "init", description: "Scaffold a HUNTER.md for this project" },
  { name: "mcp", description: "List connected MCP servers and tools" },
  { name: "exit", description: "Quit HunterCode" },
];

export interface CompletionContext {
  /** The active provider — drives which model presets `/model` suggests. */
  provider: ProviderName;
}

/** Argument values for a command, given the current context. */
function argValues(command: string, ctx: CompletionContext): string[] {
  switch (command) {
    case "mode":
      return [...MODES];
    case "provider":
      return [...PROVIDER_NAMES];
    case "apikey":
      // Ollama needs no key, so it is not a valid target.
      return PROVIDER_NAMES.filter((p) => p !== "ollama");
    case "model":
      return MODEL_PRESETS[ctx.provider].map((p) => p.value);
    case "editapproval":
    case "automode":
      return ["auto", "manual"];
    default:
      return [];
  }
}

/**
 * Compute the autocomplete suggestions for the current input line.
 *
 * - "/" or "/<partial>" (no space)  → matching command names.
 * - "/<cmd> <partial-arg>"          → that command's argument values.
 * - anything else                   → [] (no menu).
 */
export function computeSuggestions(line: string, ctx: CompletionContext): Suggestion[] {
  if (!line.startsWith("/")) return [];

  const rest = line.slice(1);
  const spaceAt = rest.indexOf(" ");

  // No space yet → still completing the command name.
  if (spaceAt === -1) {
    const partial = rest.toLowerCase();
    return COMMANDS.filter((c) => c.name.startsWith(partial)).map((c) => ({
      value: c.name,
      description: c.description,
      isCommand: true,
    }));
  }

  // We have "/<cmd> <partialArg…>" → complete the argument.
  const cmd = rest.slice(0, spaceAt).toLowerCase();
  const argPartial = rest.slice(spaceAt + 1);
  // Only suggest for the first argument token (e.g. don't re-suggest after the key).
  if (argPartial.includes(" ")) return [];

  return argValues(cmd, ctx)
    .filter((v) => v.toLowerCase().startsWith(argPartial.toLowerCase()))
    .map((v) => ({ value: v, isCommand: false }));
}

/**
 * Apply an accepted suggestion to the current line, returning the new line text.
 * Commands that take an argument get a trailing space so the next Tab continues.
 */
export function applySuggestion(line: string, s: Suggestion): string {
  if (s.isCommand) {
    const cmd = COMMANDS.find((c) => c.name === s.value);
    return "/" + s.value + (cmd?.takesArg ? " " : "");
  }
  // Argument: replace everything after the first space.
  const rest = line.slice(1);
  const spaceAt = rest.indexOf(" ");
  const cmd = spaceAt === -1 ? rest : rest.slice(0, spaceAt);
  return "/" + cmd + " " + s.value;
}

/**
 * Whether accepting this suggestion completes the input (so Enter should submit).
 * A command that takes an argument is NOT complete — it expands and waits for the
 * argument. A no-arg command, or an argument value, is complete.
 */
export function isComplete(s: Suggestion): boolean {
  if (!s.isCommand) return true;
  const cmd = COMMANDS.find((c) => c.name === s.value);
  return !cmd?.takesArg;
}
