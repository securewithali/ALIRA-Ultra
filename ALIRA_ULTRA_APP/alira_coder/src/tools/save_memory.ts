import type { Tool } from "./types.js";
import { appendMemory } from "../memory.js";
import { relative } from "node:path";

/**
 * Records an important fix into the project's memory file so future sessions
 * have the context. The agent is prompted to call this after a non-trivial
 * change, capturing what the issue was and how it was resolved.
 */
export const saveMemoryTool: Tool = {
  schema: {
    name: "save_memory",
    description:
      "Save a short summary of an important change to the project's memory (.huntercode/memory.md), so it can be recalled in future sessions. Call this after completing a non-trivial fix or feature. Include what the problem was and how you solved it.",
    parameters: {
      type: "object",
      properties: {
        title: { type: "string", description: "A short title for the entry (e.g. 'Fixed null-byte bug in grep')." },
        summary: { type: "string", description: "What the issue was and how it was fixed/implemented. A few sentences." },
      },
      required: ["title", "summary"],
    },
  },
  async execute(args, ctx) {
    const title = String(args.title ?? "").trim();
    const summary = String(args.summary ?? "").trim();
    if (!title || !summary) return "Error: both title and summary are required.";

    const path = appendMemory(ctx.cwd, { title, summary });
    return `Saved to project memory (${relative(ctx.cwd, path)}).`;
  },
};
