import { readdirSync, statSync, readFileSync, existsSync } from "node:fs";
import { resolve, join, relative } from "node:path";
import type { Tool } from "./types.js";
import { IGNORED_DIRS } from "./ignore.js";

/**
 * Recursive text search implemented in pure Node (no ripgrep dependency), so
 * it works identically across platforms. Returns `relativePath:line:match`.
 */
export const grepTool: Tool = {
  schema: {
    name: "grep",
    description:
      "Search for a regular-expression pattern across files in a directory tree, ignoring node_modules, .git, dist, etc. Returns matching lines as path:line:content.",
    parameters: {
      type: "object",
      properties: {
        pattern: { type: "string", description: "A JavaScript regular expression to search for." },
        path: { type: "string", description: "Directory or file to search. Defaults to the working directory." },
      },
      required: ["pattern"],
    },
  },
  async execute(args, ctx) {
    let regex: RegExp;
    try {
      regex = new RegExp(String(args.pattern), "i");
    } catch (e) {
      return `Error: invalid regular expression: ${(e as Error).message}`;
    }

    const target = resolve(ctx.cwd, args.path ? String(args.path) : ".");
    if (!existsSync(target)) return `Error: path not found: ${args.path ?? "."}`;

    const matches: string[] = [];
    const maxMatches = 200;
    const NUL = String.fromCharCode(0);

    const searchFile = (file: string) => {
      if (matches.length >= maxMatches) return;
      let content: string;
      try {
        content = readFileSync(file, "utf8");
      } catch {
        return; // unreadable
      }
      if (content.includes(NUL)) return; // skip binary files
      const lines = content.split("\n");
      for (let i = 0; i < lines.length; i++) {
        if (matches.length >= maxMatches) return;
        if (regex.test(lines[i])) {
          matches.push(`${relative(ctx.cwd, file)}:${i + 1}:${lines[i].trim()}`);
        }
      }
    };

    const walk = (dir: string) => {
      if (matches.length >= maxMatches) return;
      let entries: string[];
      try {
        entries = readdirSync(dir);
      } catch {
        return;
      }
      for (const name of entries) {
        if (matches.length >= maxMatches) return;
        const full = join(dir, name);
        let isDir = false;
        try {
          isDir = statSync(full).isDirectory();
        } catch {
          continue;
        }
        if (isDir) {
          if (!IGNORED_DIRS.has(name)) walk(full);
        } else {
          searchFile(full);
        }
      }
    };

    if (statSync(target).isDirectory()) walk(target);
    else searchFile(target);

    if (!matches.length) return `No matches for /${args.pattern}/`;
    const truncated = matches.length >= maxMatches ? "\n... (truncated)" : "";
    return matches.join("\n") + truncated;
  },
};
