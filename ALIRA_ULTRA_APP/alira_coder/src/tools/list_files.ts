import { readdirSync, statSync, existsSync } from "node:fs";
import { resolve, join, relative } from "node:path";
import type { Tool } from "./types.js";
import { IGNORED_DIRS } from "./ignore.js";

export const listFilesTool: Tool = {
  schema: {
    name: "list_files",
    description:
      "List files and directories within a path (recursively, up to a sensible depth), ignoring node_modules, .git, dist, __pycache__, etc. Directories are marked with a trailing slash.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Directory to list, relative to the working directory. Defaults to the working directory." },
      },
      required: [],
    },
  },
  async execute(args, ctx) {
    const root = resolve(ctx.cwd, args.path ? String(args.path) : ".");
    if (!existsSync(root)) return `Error: path not found: ${args.path ?? "."}`;
    if (!statSync(root).isDirectory()) return `Error: ${args.path} is not a directory.`;

    const results: string[] = [];
    const maxEntries = 500;
    const maxDepth = 5;

    const walk = (dir: string, depth: number) => {
      if (depth > maxDepth || results.length >= maxEntries) return;
      let entries: string[];
      try {
        entries = readdirSync(dir).sort();
      } catch {
        return;
      }
      for (const name of entries) {
        if (results.length >= maxEntries) return;
        const full = join(dir, name);
        let isDir = false;
        try {
          isDir = statSync(full).isDirectory();
        } catch {
          continue;
        }
        if (isDir && IGNORED_DIRS.has(name)) continue;
        const rel = relative(ctx.cwd, full);
        results.push(isDir ? `${rel}/` : rel);
        if (isDir) walk(full, depth + 1);
      }
    };

    walk(root, 0);
    if (!results.length) return "(empty directory)";
    const truncated = results.length >= maxEntries ? "\n... (truncated)" : "";
    return results.join("\n") + truncated;
  },
};
