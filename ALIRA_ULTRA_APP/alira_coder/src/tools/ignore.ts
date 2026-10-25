/** Directory names skipped by list_files and grep. */
export const IGNORED_DIRS = new Set([
  "node_modules",
  ".git",
  "dist",
  "__pycache__",
  ".next",
  "build",
  ".cache",
]);
