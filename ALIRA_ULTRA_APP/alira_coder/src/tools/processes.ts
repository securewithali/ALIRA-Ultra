import { spawn, type ChildProcess } from "node:child_process";

/**
 * A registry of background shell processes (dev servers, watchers, etc.) started
 * via `run_bash` with `background: true`. Output is captured into a rolling
 * buffer so `check_logs` can stream it back to the agent, and `stop_process`
 * can terminate it. Kept in-memory for the lifetime of the CLI session.
 */
export interface BgProcess {
  id: number;
  command: string;
  child: ChildProcess;
  output: string;
  readOffset: number; // for incremental log reads
  status: "running" | "exited";
  exitCode: number | null;
  startedAt: number;
}

const MAX_OUTPUT = 1_000_000; // cap the rolling buffer (~1 MB)
const processes = new Map<number, BgProcess>();
let nextId = 1;

export function startBackground(command: string, cwd: string): BgProcess {
  // detached → its own process group, so we can kill the whole tree later.
  const child = spawn(command, { cwd, shell: true, detached: true });
  const proc: BgProcess = {
    id: nextId++,
    command,
    child,
    output: "",
    readOffset: 0,
    status: "running",
    exitCode: null,
    startedAt: Date.now(),
  };

  const append = (chunk: Buffer) => {
    proc.output += chunk.toString();
    if (proc.output.length > MAX_OUTPUT) {
      proc.output = proc.output.slice(-MAX_OUTPUT);
      if (proc.readOffset > proc.output.length) proc.readOffset = 0;
    }
  };
  child.stdout?.on("data", append);
  child.stderr?.on("data", append);
  child.on("exit", (code) => {
    proc.status = "exited";
    proc.exitCode = code ?? 0;
  });
  child.on("error", (e) => {
    proc.output += `\n[spawn error: ${e.message}]`;
    proc.status = "exited";
    proc.exitCode = -1;
  });

  processes.set(proc.id, proc);
  return proc;
}

export function getProcess(id: number): BgProcess | undefined {
  return processes.get(id);
}

export function listProcesses(): BgProcess[] {
  return [...processes.values()];
}

/** Return output appended since the last read for this process. */
export function readNewOutput(proc: BgProcess): string {
  const chunk = proc.output.slice(proc.readOffset);
  proc.readOffset = proc.output.length;
  return chunk;
}

/** Terminate a running background process (and its group). Returns false if already exited. */
export function stopProcess(proc: BgProcess): boolean {
  if (proc.status === "exited") return false;
  const pid = proc.child.pid;
  try {
    if (pid) process.kill(-pid, "SIGTERM");
    else proc.child.kill("SIGTERM");
  } catch {
    try {
      proc.child.kill("SIGKILL");
    } catch {
      /* already gone */
    }
  }
  return true;
}

/** Stop every running background process (called on CLI exit). */
export function killAll(): void {
  for (const proc of processes.values()) stopProcess(proc);
}
