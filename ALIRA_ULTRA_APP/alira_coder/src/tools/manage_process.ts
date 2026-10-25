import type { Tool } from "./types.js";
import { getProcess, listProcesses, readNewOutput, stopProcess } from "./processes.js";

function statusLine(id: number): string {
  const p = getProcess(id);
  if (!p) return `No process #${id}.`;
  const age = Math.round((Date.now() - p.startedAt) / 1000);
  return p.status === "running"
    ? `#${p.id} running (${age}s): \`${p.command}\``
    : `#${p.id} exited [code ${p.exitCode}]: \`${p.command}\``;
}

function listAll(): string {
  const all = listProcesses();
  if (!all.length) return "No background processes.";
  return ["Background processes:", ...all.map((p) => "  " + statusLine(p.id))].join("\n");
}

export const checkLogsTool: Tool = {
  schema: {
    name: "check_logs",
    description:
      "Read output from a background process started by run_bash. Returns the output produced since the last check (incremental), plus whether it is still running. Omit `id` to list all background processes.",
    parameters: {
      type: "object",
      properties: {
        id: { type: "number", description: "The background process id. Omit to list all processes." },
        full: { type: "boolean", description: "Return the entire buffered output instead of only new output." },
      },
    },
  },
  async execute(args) {
    if (args.id === undefined || args.id === null) return listAll();
    const id = Number(args.id);
    const proc = getProcess(id);
    if (!proc) return `No background process #${id}.\n${listAll()}`;

    const out = args.full ? proc.output : readNewOutput(proc);
    const header = statusLine(id);
    const body = out.trim() || "(no new output)";
    return `${header}\n${body}`;
  },
};

export const stopProcessTool: Tool = {
  schema: {
    name: "stop_process",
    description: "Stop a background process started by run_bash, by its id.",
    parameters: {
      type: "object",
      properties: {
        id: { type: "number", description: "The background process id to stop." },
      },
      required: ["id"],
    },
  },
  async execute(args) {
    const id = Number(args.id);
    const proc = getProcess(id);
    if (!proc) return `No background process #${id}.\n${listAll()}`;
    const stopped = stopProcess(proc);
    return stopped
      ? `Stopped background process #${id}: \`${proc.command}\`.`
      : `Process #${id} had already exited [code ${proc.exitCode}].`;
  },
};
