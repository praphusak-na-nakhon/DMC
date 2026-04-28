import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(desktopRoot, "..", "..");
const sourcePath = path.join(repoRoot, "obec-study-form.xlsx");
const targetDir = path.join(desktopRoot, "src-tauri", "templates");
const targetPath = path.join(targetDir, "obec-study-form.xlsx");

if (!existsSync(sourcePath)) {
  throw new Error(`Template source is missing: ${sourcePath}`);
}

mkdirSync(targetDir, { recursive: true });

if (existsSync(targetPath) && readFileSync(sourcePath).equals(readFileSync(targetPath))) {
  console.log(`Template already current: ${targetPath}`);
  process.exit(0);
}

copyFileSync(sourcePath, targetPath);

const sourceSize = statSync(sourcePath).size;
const targetSize = statSync(targetPath).size;

if (sourceSize !== targetSize) {
  throw new Error(`Template copy size mismatch: ${sourceSize} != ${targetSize}`);
}

console.log(`Synced template: ${sourcePath} -> ${targetPath}`);
