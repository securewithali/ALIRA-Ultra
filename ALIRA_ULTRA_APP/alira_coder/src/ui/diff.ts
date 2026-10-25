import { theme } from "./theme.js";

/**
 * Render a simple, readable colored diff between two strings.
 *
 * This is intentionally line-oriented (not a full Myers diff): we show the
 * removed block in red and the added block in green. For HunterCode's edits
 * (a single `str_replace` or a whole-file `write_file`) that's clear enough
 * and keeps us dependency-free.
 */
export function renderDiff(oldStr: string, newStr: string): string {
  const oldLines = oldStr.length ? oldStr.split("\n") : [];
  const newLines = newStr.length ? newStr.split("\n") : [];

  const out: string[] = [];
  for (const line of oldLines) out.push(theme.removed(`- ${line}`));
  for (const line of newLines) out.push(theme.added(`+ ${line}`));
  return out.join("\n");
}

/**
 * Render a focused diff for a `str_replace`: only the changed snippet, with a
 * little context label. Old snippet in red, new snippet in green.
 */
export function renderReplaceDiff(oldSnippet: string, newSnippet: string): string {
  return renderDiff(oldSnippet, newSnippet);
}
