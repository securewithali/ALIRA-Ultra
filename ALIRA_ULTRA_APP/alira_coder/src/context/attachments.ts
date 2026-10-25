import { existsSync, readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";

/**
 * `@filename` attachments.
 *
 * When a user message mentions `@path/to/file`, we read that file and inject its
 * contents (with line numbers, matching read_file) as a context block ahead of
 * the message — so the model has the file without spending a tool call. Multiple
 * mentions all load; a non-existent path produces a clean warning, never a crash.
 */

const MENTION_RE = /(^|\s)@([^\s@]+)/g;
const MAX_BYTES = 200_000; // guard against attaching something huge

export interface AttachResult {
  /** The message to send (context blocks prepended; original text preserved). */
  text: string;
  /** Human-readable warnings for mentions that couldn't be loaded. */
  warnings: string[];
}

/** Number a file's contents the same way `read_file` does. */
function numbered(content: string): string {
  const lines = content.split("\n");
  const width = String(lines.length).length;
  return lines.map((line, i) => `${String(i + 1).padStart(width, " ")}\t${line}`).join("\n");
}

export function parseAttachments(input: string, cwd: string): AttachResult {
  const warnings: string[] = [];
  const blocks: string[] = [];
  const seen = new Set<string>();

  let m: RegExpExecArray | null;
  MENTION_RE.lastIndex = 0;
  while ((m = MENTION_RE.exec(input)) !== null) {
    const raw = m[2];
    // A trailing sentence punctuation isn't part of the path ("@file.ts?").
    const stripped = raw.replace(/[?.,:;!)\]'"]+$/, "");
    const rel = existsSync(resolve(cwd, raw)) ? raw : stripped;
    if (seen.has(rel)) continue;
    seen.add(rel);

    const abs = resolve(cwd, rel);
    if (!existsSync(abs)) {
      warnings.push(`⚠ @${rel}: file not found — ignoring.`);
      continue;
    }
    try {
      const st = statSync(abs);
      if (st.isDirectory()) {
        warnings.push(`⚠ @${rel}: is a directory — ignoring.`);
        continue;
      }
      if (st.size > MAX_BYTES) {
        warnings.push(`⚠ @${rel}: too large (${st.size} bytes) — ignoring.`);
        continue;
      }
      const content = readFileSync(abs, "utf8");
      blocks.push(`--- FILE: ${rel} ---\n${numbered(content)}\n--- END FILE: ${rel} ---`);
    } catch (e) {
      warnings.push(`⚠ @${rel}: ${(e as Error).message} — ignoring.`);
    }
  }

  if (!blocks.length) return { text: input, warnings };
  return {
    text: `${blocks.join("\n\n")}\n\nUsing the attached file context above, respond to:\n${input}`,
    warnings,
  };
}
