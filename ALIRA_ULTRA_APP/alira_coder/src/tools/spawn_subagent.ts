import type { Tool } from "./types.js";

/**
 * Dispatches a sub-agent to handle an isolated chunk of a larger job. The main
 * agent breaks work into pieces, spawns a sub-agent per piece with only the
 * relevant context, and reads back each result (also written to shared memory).
 *
 * Gated behind config (`subagents.enabled`) — powerful on strong models, flaky
 * on weak ones — so the tool reports cleanly when dispatch is unavailable.
 */
export const spawnSubagentTool: Tool = {
  schema: {
    name: "spawn_subagent",
    description:
      "Dispatch a focused sub-agent to complete one isolated sub-task and return its result. Use for parallelizable or self-contained chunks of a larger job. Give it a clear task and only the context it needs (NOT the whole history). Results are shared with other agents.",
    parameters: {
      type: "object",
      properties: {
        task: { type: "string", description: "The single, focused task for the sub-agent." },
        context: {
          type: "string",
          description: "Just the relevant slice of context the sub-agent needs (file paths, decisions, constraints).",
        },
      },
      required: ["task"],
    },
  },
  async execute(args, ctx) {
    if (!ctx.spawnSubagent) {
      return "Sub-agents are disabled. Enable them via subagents.enabled in ~/.huntercode/config.json, or complete the task yourself.";
    }
    const task = String(args.task ?? "").trim();
    if (!task) return "Error: task is required.";
    const context = args.context ? String(args.context) : undefined;
    return ctx.spawnSubagent(task, context);
  },
};
