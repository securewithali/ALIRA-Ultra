import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { IGNORED_DIRS } from "./tools/ignore.js";

/**
 * Scaffold a starter `ALIRA_CODER.md` by scanning the project: package metadata,
 * detected languages, the package manager (from lockfiles), useful scripts, and
 * the top-level layout. Mirrors Claude Code's `/init`. Returns the markdown.
 */
export function scaffoldALIRACoderMd(cwd: string): string {
  const lines: string[] = ["# ALIRA_CODER.md — Project Notes", ""];

  // package.json metadata + scripts.
  const pkgPath = join(cwd, "package.json");
  let pkg: any = null;
  if (existsSync(pkgPath)) {
    try {
      pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
    } catch {
      pkg = null;
    }
  }
  if (pkg?.name) lines.push(`**Project:** ${pkg.name}${pkg.version ? ` v${pkg.version}` : ""}`);
  if (pkg?.description) lines.push("", pkg.description);

  // Package manager from lockfiles.
  const pm = detectPackageManager(cwd);
  if (pm) lines.push("", `**Package manager:** ${pm}`);

  // Languages from file extensions present at the top levels.
  const langs = detectLanguages(cwd);
  if (langs.length) lines.push("", `**Languages:** ${langs.join(", ")}`);

  // Useful npm scripts.
  if (pkg?.scripts && Object.keys(pkg.scripts).length) {
    lines.push("", "## Common commands", "");
    const run = pm === "npm" || !pm ? "npm run" : pm;
    for (const name of ["dev", "start", "build", "test", "lint"]) {
      if (pkg.scripts[name]) lines.push(`- \`${run} ${name}\` — ${pkg.scripts[name]}`);
    }
  }

  // Top-level layout.
  const dirs = topLevelDirs(cwd);
  if (dirs.length) {
    lines.push("", "## Layout", "");
    for (const d of dirs) lines.push(`- \`${d}/\``);
  }

  lines.push(
    "",
    "## Notes",
    "",
    "_HunterCode loads this file every session. Add durable conventions here_",
    "_(or let the agent append them via the `remember` tool)._",
    "",
  );
  return lines.join("\n");
}

function detectPackageManager(cwd: string): string | null {
  if (existsSync(join(cwd, "pnpm-lock.yaml"))) return "pnpm";
  if (existsSync(join(cwd, "yarn.lock"))) return "yarn";
  if (existsSync(join(cwd, "bun.lockb"))) return "bun";
  if (existsSync(join(cwd, "package-lock.json"))) return "npm";
  return null;
}

const EXT_LANG: Record<string, string> = {
  ts: "TypeScript",
  tsx: "TypeScript (React)",
  js: "JavaScript",
  jsx: "JavaScript (React)",
  py: "Python",
  go: "Go",
  rs: "Rust",
  java: "Java",
  rb: "Ruby",
  php: "PHP",
  c: "C",
  cpp: "C++",
  cs: "C#",
};

function detectLanguages(cwd: string): string[] {
  const found = new Set<string>();
  const walk = (dir: string, depth: number) => {
    if (depth > 2) return;
    let entries: string[];
    try {
      entries = readdirSync(dir);
    } catch {
      return;
    }
    for (const name of entries) {
      if (IGNORED_DIRS.has(name) || name.startsWith(".")) continue;
      const full = join(dir, name);
      let st;
      try {
        st = statSync(full);
      } catch {
        continue;
      }
      if (st.isDirectory()) walk(full, depth + 1);
      else {
        const ext = name.split(".").pop()?.toLowerCase() ?? "";
        if (EXT_LANG[ext]) found.add(EXT_LANG[ext]);
      }
    }
  };
  walk(cwd, 0);
  return [...found];
}

function topLevelDirs(cwd: string): string[] {
  try {
    return readdirSync(cwd)
      .filter((n) => !IGNORED_DIRS.has(n) && !n.startsWith("."))
      .filter((n) => {
        try {
          return statSync(join(cwd, n)).isDirectory();
        } catch {
          return false;
        }
      })
      .slice(0, 12);
  } catch {
    return [];
  }
}
