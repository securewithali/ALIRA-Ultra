import type { Tool } from "./types.js";
import { MODES } from "../modes.js";

/**
 * Lets the agent change its own operating mode mid-task — e.g. notice a request
 * is complex and switch from `agent` to `plan` first. Whether this needs the
 * user's permission depends on the `autoMode` setting: "manual" prompts the
 * user, "auto" switches and just informs. Routed through ctx.requestModeSwitch.
 */
export const setModeTool: Tool = {
  schema: {
    name: "set_mode",
    description:
      "Switch your operating mode when the task calls for it. Use 'plan' when a request touches multiple files, needs several sequential steps, or is ambiguous (investigate and propose a plan first). Use 'agent' to act and make changes. Use 'ask' for a pure question. Provide a brief reason.",
    parameters: {
      type: "object",
      properties: {
        mode: { type: "string", enum: MODES, description: "Target mode: agent, plan, or ask." },
        reason: { type: "string", description: "One short sentence on why this mode fits." },
      },
      required: ["mode", "reason"],
    },
  },
  async execute(args, ctx) {
    const mode = String(args.mode ?? "").trim();
    const reason = String(args.reason ?? "").trim();
    if (!MODES.includes(mode as any)) {
      return `Error: unknown mode "${mode}". Choose one of: ${MODES.join(", ")}.`;
    }
    const switched = await ctx.requestModeSwitch(mode, reason);
    return switched
      ? `Switched to ${mode} mode.`
      : `Mode switch to ${mode} was declined; staying in the current mode.`;
  },
};
