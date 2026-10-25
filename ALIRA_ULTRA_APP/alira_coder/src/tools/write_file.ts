import { writeFileSync, existsSync, readFileSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import type { Tool } from "./types.js";
import { renderDiff } from "../ui/diff.js";

export const writeFileTool: Tool = {
  schema: {
    name: "write_file",
    description:
      "Create a new file or overwrite an existing one with the given content. Creates parent directories as needed.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file, relative to the working directory or absolute." },
        content: { type: "string", description: "The full content to write to the file." },
      },
      required: ["path", "content"],
    },
  },
  async execute(args, ctx) {
    const path = resolve(ctx.cwd, String(args.path));
    const content = String(args.content ?? "");
    const existed = existsSync(path);
    const previous = existed ? readFileSync(path, "utf8") : "";

    if (!existed || previous !== content) {
      const decision = await ctx.approveEdit(String(args.path), renderDiff(previous, content));
      if (decision === "no")
        return `Write to ${args.path} was rejected by the user. Do not retry it unless asked.`;
    }

    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, content, "utf8");

    const lines = content.split("\n").length;
    return existed
      ? `Overwrote ${args.path} (${lines} lines).`
      : `Created ${args.path} (${lines} lines).`;
  },
};
