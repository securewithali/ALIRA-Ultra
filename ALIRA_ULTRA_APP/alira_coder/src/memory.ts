import { existsSync, mkdirSync, readFileSync, appendFileSync } from "node:fs";
import { join, dirname } from "node:path";

/**
 * Per-project memory — a small Markdown log that lives inside the project
 * (so it travels with the repo, like Claude Code's CLAUDE.md). After an
 * important fix the agent records what the issue was and how it was solved;
 * on future sessions that history is loaded back into the system prompt.
 */

export function memoryPath(cwd: string): string {
  return join(cwd, ".ALIRA-codercode", "memory.md");
}

/** Path to the user-facing project memory file (like Claude Code's CLAUDE.md). */
export function ALIRACoderPath(cwd: string): string {
  return join(cwd, "HUNTER.md");
}

function readIfExists(path: string): string {
  if (!existsSync(path)) return "";
  try {
    return readFileSync(path, "utf8").trim();
  } catch {
    return "";
  }
}

/**
 * Read the combined project memory: the durable `HUNTER.md` (project root) plus
 * the agent's dated fix log (`.ALIRA-codercode/memory.md`). Returns "" if neither
 * exists. Both are loaded into the system prompt on startup.
 */
export function loadMemory(cwd: string): string {
  const hunter = readIfExists(ALIRACoderPath(cwd));
  const log = readIfExists(memoryPath(cwd));
  const parts: string[] = [];
  if (hunter) parts.push(hunter);
  if (log) parts.push(log);
  return parts.join("\n\n");
}

/** Append a durable note to HUNTER.md, creating it (with a header) if needed. */
export function appendHunterNote(cwd: string, note: string): string {
  const path = ALIRACoderPath(cwd);
  const isNew = !existsSync(path);
  const header = isNew ? "# HUNTER.md — Project Notes\n\n_Durable instructions for HunterCode._\n\n" : "";
  appendFileSync(path, `${header}- ${note}\n`, "utf8");
  return path;
}

/** Append a dated entry to the project memory, creating the file if needed. */
export function appendMemory(
  cwd: string,
  entry: { title: string; summary: string },
): string {
  const path = memoryPath(cwd);
  mkdirSync(dirname(path), { recursive: true });

  const isNew = !existsSync(path);
  const date = new Date().toISOString().slice(0, 10);
  const header = isNew ? "# HunterCode — Project Memory\n\n" : "";
  const block = `## ${entry.title}\n_${date}_\n\n${entry.summary}\n\n`;

  appendFileSync(path, header + block, "utf8");
  return path;
}
