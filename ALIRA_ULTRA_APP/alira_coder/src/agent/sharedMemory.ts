/**
 * The shared memory box for sub-agents.
 *
 * A bounded, in-session append-log that the main agent and every sub-agent can
 * read and write, so findings flow between them without passing the full
 * transcript around. Strictly size-capped (entry count + total characters) to
 * keep token usage from running away — the whole point of sub-agents is to
 * stay lean, so this evicts the oldest entries once it fills.
 */

export interface MemoryEntry {
  agent: string;
  note: string;
}

export class SharedMemory {
  private entries: MemoryEntry[] = [];

  constructor(private maxEntries = 40, private maxChars = 8_000) {}

  /** Append a note from an agent, evicting oldest entries past the caps. */
  write(agent: string, note: string): void {
    const trimmed = note.trim();
    if (!trimmed) return;
    this.entries.push({ agent, note: trimmed });
    while (this.entries.length > this.maxEntries) this.entries.shift();
    while (this.totalChars() > this.maxChars && this.entries.length > 1) this.entries.shift();
  }

  /** A formatted snapshot for injecting into an agent's context, or "". */
  read(): string {
    if (!this.entries.length) return "";
    return this.entries.map((e) => `- [${e.agent}] ${e.note}`).join("\n");
  }

  get size(): number {
    return this.entries.length;
  }

  private totalChars(): number {
    return this.entries.reduce((n, e) => n + e.note.length + e.agent.length + 6, 0);
  }
}
