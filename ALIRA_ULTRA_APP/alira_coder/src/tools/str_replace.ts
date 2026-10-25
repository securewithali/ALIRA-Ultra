import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import type { Tool } from "./types.js";
import { renderReplaceDiff } from "../ui/diff.js";

/**
 * The core editing mechanism. Finds an EXACT `old_string` that must appear
 * exactly once, then replaces it. No line-number-based editing — this keeps
 * edits unambiguous and robust to a model miscounting lines.
 */
export const strReplaceTool: Tool = {
  schema: {
    name: "str_replace",
    description:
      "Replace an exact string in a file. `old_string` must match the file content EXACTLY (including whitespace) and must appear exactly once. If it appears zero times or multiple times, the edit fails and you should provide more surrounding context to make it unique.",
    parameters: {
      type: "object",
      properties: {
        path: { type: "string", description: "Path to the file, relative to the working directory or absolute." },
        old_string: { type: "string", description: "The exact text to find. Include enough context to be unique." },
        new_string: { type: "string", description: "The text to replace it with." },
      },
      required: ["path", "old_string", "new_string"],
    },
  },
  async execute(args, ctx) {
    const path = resolve(ctx.cwd, String(args.path));
    const oldStr = String(args.old_string ?? "");
    const newStr = String(args.new_string ?? "");

    if (!existsSync(path)) return `Error: file not found: ${args.path}`;
    if (oldStr === "") return `Error: old_string must not be empty.`;

    const content = readFileSync(path, "utf8");
    const count = content.split(oldStr).length - 1;

    if (count === 0) {
      return `Error: old_string not found in ${args.path}. The text must match exactly, including whitespace and indentation.`;
    }
    if (count > 1) {
      return `Error: old_string appears ${count} times in ${args.path}. Add more surrounding context so it matches exactly one location.`;
    }

    const updated = content.replace(oldStr, newStr);

    const decision = await ctx.approveEdit(String(args.path), renderReplaceDiff(oldStr, newStr));
    if (decision === "no") return `Edit to ${args.path} was rejected by the user. Do not retry it unless asked.`;

    writeFileSync(path, updated, "utf8");
    return `Edited ${args.path} (1 replacement).`;
  },
};
