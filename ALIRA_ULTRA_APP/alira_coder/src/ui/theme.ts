import chalk from "chalk";

/**
 * The HunterCode palette. Warm orange is the primary accent throughout,
 * inspired by Claude's branding.
 */
export const colors = {
  primary: "#FF8C42", // warm orange — banners, prompts
  accent: "#FF6B35", // deeper orange — highlights, tool calls
  dim: "#8A8A8A",
  added: "#4ADE80", // diff additions
  removed: "#F87171", // diff deletions
  error: "#EF4444",
  info: "#60A5FA",
};

export const theme = {
  primary: (s: string) => chalk.hex(colors.primary)(s),
  accent: (s: string) => chalk.hex(colors.accent)(s),
  bold: (s: string) => chalk.hex(colors.primary).bold(s),
  dim: (s: string) => chalk.hex(colors.dim)(s),
  added: (s: string) => chalk.hex(colors.added)(s),
  removed: (s: string) => chalk.hex(colors.removed)(s),
  error: (s: string) => chalk.hex(colors.error)(s),
  info: (s: string) => chalk.hex(colors.info)(s),

  /** The interactive prompt, e.g. "hunter › ". */
  prompt: () => chalk.hex(colors.primary).bold("hunter") + chalk.hex(colors.accent)(" › "),

  /** A live tool-call indicator, e.g. "→ Reading main.ts". */
  toolCall: (label: string) => chalk.hex(colors.accent)("→ ") + chalk.hex(colors.primary)(label),
};
