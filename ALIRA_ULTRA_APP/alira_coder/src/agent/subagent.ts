import type { Config } from "../config.js";
import type { Message, Provider } from "../types.js";
import type { AgentUI } from "../agent.js";
import {
  tools,
  schemasFor,
  toolLabel,
  toolResultSummary,
  isErrorResult,
} from "../tools/index.js";
import type { ToolContext } from "../tools/index.js";
import { AGENT_TOOLS } from "../modes.js";
import type { SharedMemory } from "./sharedMemory.js";
import { maybeCompact } from "./compaction.js";

/**
 * Runs a single sub-agent: a focused, self-contained mini agent loop dispatched
 * by the main agent for an isolated sub-task. It gets ONLY a scoped context (not
 * the full transcript), shares the same tools, auto-approves its edits, and
 * writes a structured result + findings into the shared memory box. Rendered as
 * a nested panel so its activity is visible without dominating the output.
 *
 * Sub-agents cannot spawn further sub-agents (no recursion) and skip mode
 * switching — they stay in a focused agent role.
 */

const MAX_ITERATIONS = 15;

// Sub-agents get the acting toolset, minus self-direction/recursion tools.
const SUBAGENT_TOOLS = AGENT_TOOLS.filter(
  (t) => t !== "spawn_subagent" && t !== "set_mode" && t !== "remember",
).concat("update_todos");

export interface SubagentDeps {
  provider: Provider;
  config: Config;
  cwd: string;
  ui: AgentUI;
  shared: SharedMemory;
  /** Confirm callback (sub-agent edits auto-apply, but confirm is still wired). */
  confirm: (q: string) => Promise<boolean>;
}

export async function runSubagent(
  id: number,
  task: string,
  context: string | undefined,
  deps: SubagentDeps,
): Promise<string> {
  const agentName = `subagent-${id}`;
  const shared = deps.shared.read();

  const system = [
    "You are a focused sub-agent within HunterCode. You have been given ONE isolated task.",
    "Complete it directly and efficiently using your tools, then stop with a short result.",
    "Do not ask the user questions — act on reasonable assumptions.",
    "When you discover something other agents should know (a decision, an interface, a gotcha),",
    "include it clearly in your final summary; it will be saved to shared memory.",
    `Working directory: ${deps.cwd}`,
    context ? `\nScoped context:\n${context}` : "",
    shared ? `\nShared memory (from other agents):\n${shared}` : "",
  ].join("\n");

  const messages: Message[] = [
    { role: "system", content: system },
    { role: "user", content: task },
  ];

  const ctx: ToolContext = {
    cwd: deps.cwd,
    confirm: deps.confirm,
    print: (line) => deps.ui.print("    " + line),
    approveEdit: async (_path, diff) => {
      deps.ui.onDiff?.(diff);
      return "yes"; // sub-agents act autonomously
    },
    setTodos: (todos) => deps.ui.onTodos?.(todos),
    requestModeSwitch: async () => false, // sub-agents don't switch modes
  };

  const allowed = SUBAGENT_TOOLS;
  const schemas = schemasFor(allowed);
  let finalText = "";

  for (let i = 0; i < MAX_ITERATIONS; i++) {
    await maybeCompact(messages, deps.provider, deps.config, deps.ui, false);
    deps.ui.setStatus?.(`Sub-agent ${id}`);
    const response = await deps.provider.chatStream(
      messages,
      schemas,
      { model: deps.config.model, temperature: deps.config.temperature },
      { onText: () => {} }, // keep sub-agent prose out of the main stream
    );
    deps.ui.setStatus?.(null);

    messages.push({
      role: "assistant",
      content: response.content,
      toolCalls: response.toolCalls.length ? response.toolCalls : undefined,
    });

    if (!response.toolCalls.length) {
      finalText = response.content;
      break;
    }

    for (const call of response.toolCalls) {
      deps.ui.onToolCall?.("  " + toolLabel(call.name, call.arguments));
      let result: string;
      const tool = tools[call.name];
      if (!tool || !allowed.includes(call.name)) {
        result = `Error: tool "${call.name}" is not available to sub-agents.`;
      } else {
        try {
          result = await tool.execute(call.arguments, ctx);
        } catch (e) {
          result = `Error executing ${call.name}: ${(e as Error).message}`;
        }
      }
      const ok = !isErrorResult(result);
      deps.ui.onToolResult?.(toolResultSummary(call.name, result, ok), ok);
      messages.push({ role: "tool", content: result, toolCallId: call.id, name: call.name });
    }
  }

  const summary = finalText.trim() || "Sub-agent finished with no summary.";
  deps.shared.write(agentName, `Task: ${task}\nResult: ${summary}`);
  return summary;
}
