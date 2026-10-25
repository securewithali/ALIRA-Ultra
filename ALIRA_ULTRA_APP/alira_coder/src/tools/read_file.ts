import { readFileSync, existsSync, statSync } from "node:fs";
import { resolve } from "node:path";
import type { Tool } from "./types.js";

export const readFileTool: Tool = {
  schema: {
    name: "read_file",
    description:
      "Read a text file and return its contents with line numbers prepended (for reference only; line numbers are NOT part of the file). Supports offset/limit for large files.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file, relative to the working directory or absolute." },
        offset: { type: "number", description: "1-based line number to start reading from (optional)." },
        limit: { type: "number", description: "Maximum number of lines to read (optional)." },
      },
      required: ["path"],
    },
  },
  async execute(args, ctx) {
    const path = resolve(ctx.cwd, String(args.path));
    if (!existsSync(path)) return `Error: file not found: ${args.path}`;
    if (statSync(path).isDirectory()) return `Error: ${args.path} is a directory, not a file.`;

    const content = readFileSync(path, "utf8");
    const allLines = content.split("\n");

    const offset = args.offset ? Math.max(1, Number(args.offset)) : 1;
    const limit = args.limit ? Number(args.limit) : allLines.length;
    const start = offset - 1;
    const end = Math.min(allLines.length, start + limit);

    const width = String(end).length;
    const numbered = allLines
      .slice(start, end)
      .map((line, i) => `${String(start + i + 1).padStart(width, " ")}\t${line}`)
      .join("\n");

    const header =
      offset > 1 || end < allLines.length
        ? `(lines ${offset}-${end} of ${allLines.length})\n`
        : "";
    return header + numbered;
  },
};
