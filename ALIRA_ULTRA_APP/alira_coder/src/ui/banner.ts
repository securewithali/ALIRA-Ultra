import chalk from "chalk";
import { colors } from "./theme.js";

// Enhanced "ALIRA Coder" ASCII art with better proportions and styling
const ART: string[] = [
  "  ███╗   ███╗██╗   ██╗██████╗  █████╗     ██████╗ ██████╗ ██████╗ ███████╗██████╗ ",
  "  ████╗ ████║╚██╗ ██╔╝██╔══██╗██╔══██╗   ██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗",
  "  ██╔████╔██║ ╚████╔╝ ██████╔╝███████║   ██║     ██║   ██║██████╔╝█████╗  ██████╔╝",
  "  ██║╚██╔╝██║  ╚██╔╝  ██╔══██╗██╔══██║   ██║     ██║   ██║██╔══██╗██╔══╝  ██╔══██╗",
  "  ██║ ╚═╝ ██║   ██║   ██║  ██║██║  ██║   ╚██████╗╚██████╔╝██║  ██║███████╗██║  ██║",
  "  ╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝    ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝",
];

const ART_WIDTH = Math.max(...ART.map((l) => l.length));

/**
 * Creates a stylish separator with gradient-like effect
 */
function separator(width: number): string {
  const w = Math.max(20, Math.min(width - 2, ART_WIDTH + 10));
  const left = Math.floor((w - 2) / 2);
  const right = w - 2 - left;

  // Create gradient effect with different characters
  const bar = "─".repeat(left) + "✦" + "─".repeat(right);
  return chalk.hex(colors.accent).dim(bar);
}

/**
 * Generates a decorative border line
 */
function borderLine(width: number): string {
  const w = Math.max(20, Math.min(width - 2, ART_WIDTH + 10));
  return chalk.hex(colors.accent).dim("╭" + "─".repeat(w) + "╮");
}

/**
 * Enhanced startup banner with modern UI elements
 */
export function banner(version: string): string {
  const cols = process.stdout.columns || 80;
  const isWide = cols >= ART_WIDTH;

  let wordmark: string;
  let versionTag: string;

  if (isWide) {
    // Full ASCII art with gradient coloring
    wordmark = ART.map((line, i) => {
      // Create gradient from primary to accent color
      const ratio = i / (ART.length - 1);
      const hex = i % 2 === 0 ? colors.primary : colors.accent;
      return chalk.hex(hex).bold(line);
    }).join("\n");

    versionTag = chalk.hex(colors.accent).dim(`  v${version}`);
  } else {
    // Compact mobile version with emoji
    const compact = [
      chalk.hex(colors.primary).bold("╔══════════════════╗"),
      chalk.hex(colors.primary).bold("║  ✦  ALIRA Coder  ✦  ║"),
      chalk.hex(colors.accent).dim(`║     v${version}     ║`),
      chalk.hex(colors.primary).bold("╚══════════════════╝"),
    ].join("\n");
    wordmark = compact;
    versionTag = "";
  }

  // Build the banner with decorative elements
  const parts: string[] = [];

  // Top border for wide screens
  if (isWide) {
    parts.push(chalk.hex(colors.primary).dim("╭" + "─".repeat(ART_WIDTH + 4) + "╮"));
    parts.push(chalk.hex(colors.primary).dim("│") + " " + wordmark + " " + chalk.hex(colors.primary).dim("│"));
    parts.push(chalk.hex(colors.primary).dim("╰" + "─".repeat(ART_WIDTH + 4) + "╯"));
  } else {
    parts.push(wordmark);
  }

  // Separator with decorative elements
  parts.push("");
  parts.push(separator(cols));

  // Add a tagline or status
  if (isWide) {
    const statusLine = `  ${chalk.hex(colors.primary)("◈")}  ${chalk.hex(colors.accent)("ready")}  ${chalk.hex(colors.primary)("◈")}  ${chalk.dim("─")}  ${chalk.hex(colors.accent)(versionTag)}`;
    parts.push(chalk.dim(statusLine));
    parts.push("");
  }

  return `\n${parts.join("\n")}\n`;
}

/**
 * Alternative compact banner for CLI tools
 */
export function compactBanner(version: string): string {
  const cols = process.stdout.columns || 80;
  const separator = "─".repeat(Math.min(30, cols - 2));

  return `
${chalk.hex(colors.primary).bold("✦")} ${chalk.hex(colors.accent).bold("ALIRA Coder")} ${chalk.dim(`v${version}`)}
${chalk.hex(colors.primary).dim(separator)}
${chalk.dim("  ⚡ powered by TypeScript")}
`.trim();
}

/**
 * Returns a minimal banner for silent/script mode
 */
export function minimalBanner(version: string): string {
  return chalk.hex(colors.accent)(`ALIRA Coder v${version}`);
}