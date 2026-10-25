import type { Tool } from "./types.js";
import type { TodoItem, TodoStatus } from "../ui/renderer.js";

const STATUSES: TodoStatus[] = ["pending", "in_progress", "completed", "failed"];

/**
 * The agent's task-planning tool. For any non-trivial, multi-step request the
 * agent first lays out a plan as a todo list, then flips each item's status as
 * it works. The list is rendered as a live panel (see renderer.todos). This is
 * best-effort: strong models drive it reliably, weak models may ignore it.
 */
export const updateTodosTool: Tool = {
  schema: {
    name: "update_todos",
    description:
      "Create or update the visible task list for a multi-step request. Call this FIRST to lay out the plan, then call it again to update statuses as you work. Keep EXACTLY ONE task 'in_progress' at a time; mark tasks 'completed' or 'failed' as you finish them. Pass the FULL list every time (it replaces the previous list).",
    parameters: {
      type: "object",
      properties: {
        todos: {
          type: "array",
          description: "The complete, ordered task list.",
          items: {
            type: "object",
            properties: {
              id: { type: "string", description: "Stable id for the task." },
              content: { type: "string", description: "Short imperative task description." },
              status: {
                type: "string",
                enum: STATUSES,
                description: "One of: pending, in_progress, completed, failed.",
              },
            },
            required: ["id", "content", "status"],
          },
        },
      },
      required: ["todos"],
    },
  },
  async execute(args, ctx) {
    const raw = Array.isArray(args.todos) ? args.todos : [];
    const todos: TodoItem[] = raw.map((t: any, i: number) => ({
      id: String(t?.id ?? i + 1),
      content: String(t?.content ?? "").trim() || `Task ${i + 1}`,
      status: STATUSES.includes(t?.status) ? t.status : "pending",
    }));
    if (!todos.length) return "Error: todos must be a non-empty array.";

    ctx.setTodos(todos);

    const done = todos.filter((t) => t.status === "completed").length;
    const active = todos.find((t) => t.status === "in_progress");
    return `Task list updated (${done}/${todos.length} done${active ? `, now: ${active.content}` : ""}).`;
  },
};
