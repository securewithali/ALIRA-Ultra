import type { Tool } from "./types.js";
import { appendHunterNote } from "../memory.js";
import { relative } from "node:path";

/**
 * Persists a durable, project-level instruction or learned fact to `HUNTER.md`
 * in the project root (loaded into context on every future session). Distinct
 * from `save_memory`, which logs a dated record of a specific fix. Confirmed
 * with the user before writing.
 */
export const rememberTool: Tool = {
  schema: {
    name: "remember",
    description:
      "Save a durable project instruction or learned fact to HUNTER.md so it is loaded in every future session (e.g. 'This project uses pnpm, not npm', 'Run tests with `npm test`'). Use for lasting conventions, NOT for a record of one fix (use save_memory for that).",
    parameters: {
      type: "object",
      properties: {
        note: { type: "string", description: "The durable instruction/fact to remember. One or two sentences." },
      },
      required: ["note"],
    },
  },
  async execute(args, ctx) {
    const note = String(args.note ?? "").trim();
    if (!note) return "Error: note must not be empty.";

    const ok = await ctx.confirm(`Save to HUNTER.md: "${note}"?`);
    if (!ok) return "User declined to save the note.";

    const path = appendHunterNote(ctx.cwd, note);
    return `Saved to project notes (${relative(ctx.cwd, path) || "HUNTER.md"}).`;
  },
};
