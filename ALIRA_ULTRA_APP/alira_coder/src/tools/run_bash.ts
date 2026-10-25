import { spawn } from "node:child_process";
import type { Tool } from "./types.js";
import { startBackground, readNewOutput } from "./processes.js";

/** Patterns that warrant an explicit confirmation before running. */
const DESTRUCTIVE = [
  /\brm\s+-[a-z]*r/i, // rm -r / rm -rf
  /\brmdir\b/i,
  /\bgit\s+push\b.*--force/i,
  /\bgit\s+reset\s+--hard\b/i,
  /\bgit\s+clean\b/i,
  /\bmkfs\b/i,
  /\bdd\s+if=/i,
  /\bsudo\b/i,
  /\bshutdown\b/i,
  /\breboot\b/i,
  /:\s*>\s*\//, // truncate a file
  />\s*\/dev\/sd/i,
];

function isDestructive(command: string): boolean {
  return DESTRUCTIVE.some((re) => re.test(command));
}

const FG_TIMEOUT = 120_000; // 2 min for foreground commands
const MAX_OUTPUT = 200_000; // cap the result fed back to the model

/** Run a foreground command, streaming its output live to the UI. */
function runForeground(
  command: string,
  cwd: string,
  stream?: (chunk: string) => void,
): Promise<string> {
  return new Promise((resolve) => {
    const child = spawn(command, { cwd, shell: true });
    let output = "";
    let timedOut = false;

    const onData = (chunk: Buffer) => {
      const s = chunk.toString();
      output += s;
      stream?.(s);
    };
    child.stdout?.on("data", onData);
    child.stderr?.on("data", onData);

    const timer = setTimeout(() => {
      timedOut = true;
      try {
        child.kill("SIGKILL");
      } catch {
        /* ignore */
      }
    }, FG_TIMEOUT);

    const done = (note: string) => {
      clearTimeout(timer);
      let out = output.trim();
      if (out.length > MAX_OUTPUT) out = "…(truncated)…\n" + out.slice(-MAX_OUTPUT);
      if (note) out = (out ? out + "\n" : "") + note;
      resolve(out || "(no output)");
    };

    child.on("error", (e) => done(`[spawn error: ${e.message}]`));
    child.on("close", (code) => {
      if (timedOut) {
        done(
          `[timed out after ${FG_TIMEOUT / 1000}s and was killed. For long-running processes (dev servers, watchers), call run_bash again with "background": true]`,
        );
      } else {
        done(code ? `[exit code: ${code}]` : "");
      }
    });
  });
}

export const runBashTool: Tool = {
  schema: {
    name: "run_bash",
    description:
      "Run a shell command in the working directory. By default it runs in the foreground and returns stdout, stderr, and the exit code (with live output). " +
      "For long-running processes that do not exit on their own — dev servers, watchers, `npm run dev`, `flask run`, `vite` — pass \"background\": true: it starts the process, returns immediately with a process id, and keeps running. Use `check_logs` to read its output and `stop_process` to stop it. " +
      "Destructive commands (rm -rf, git push --force, sudo, etc.) require user confirmation.",
    parameters: {
      type: "object",
      properties: {
        command: { type: "string", description: "The shell command to execute." },
        background: {
          type: "boolean",
          description:
            "Run as a long-lived background process (for dev servers/watchers). Returns a process id instead of waiting for it to finish.",
        },
      },
      required: ["command"],
    },
  },
  async execute(args, ctx) {
    const command = String(args.command ?? "").trim();
    if (!command) return "Error: empty command.";

    if (isDestructive(command)) {
      const ok = await ctx.confirm(`Run potentially destructive command?\n  ${command}`);
      if (!ok) return "Command cancelled by user.";
    }

    if (args.background) {
      const proc = startBackground(command, ctx.cwd);
      // Give it a moment to emit startup output / fail fast.
      await new Promise((r) => setTimeout(r, 800));
      const initial = readNewOutput(proc).trim();
      ctx.stream?.(initial ? initial + "\n" : "");
      if (proc.status === "exited") {
        return (
          `Background process #${proc.id} exited immediately [exit code: ${proc.exitCode}].\n` +
          (initial || "(no output)")
        );
      }
      return (
        `Started background process #${proc.id}: \`${command}\` (still running).\n` +
        (initial ? initial + "\n" : "") +
        `Use check_logs with id ${proc.id} to read more output, or stop_process to stop it.`
      );
    }

    return runForeground(command, ctx.cwd, ctx.stream);
  },
};
