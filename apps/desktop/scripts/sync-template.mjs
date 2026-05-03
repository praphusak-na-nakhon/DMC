import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(desktopRoot, "..", "..");
const targetDir = path.join(desktopRoot, "src-tauri", "templates");
mkdirSync(targetDir, { recursive: true });

const templates = ["obec-study-form.xlsx", "P-SAR-form.docx"];
let changed = false;

for (const templateName of templates) {
  const sourcePath = path.join(repoRoot, templateName);
  const targetPath = path.join(targetDir, templateName);

  if (!existsSync(sourcePath)) {
    throw new Error(`Template source is missing: ${sourcePath}`);
  }

  if (existsSync(targetPath) && readFileSync(sourcePath).equals(readFileSync(targetPath))) {
    console.log(`Template already current: ${targetPath}`);
    continue;
  }

  copyFileSync(sourcePath, targetPath);

  const sourceSize = statSync(sourcePath).size;
  const targetSize = statSync(targetPath).size;

  if (sourceSize !== targetSize) {
    throw new Error(`Template copy size mismatch for ${templateName}: ${sourceSize} != ${targetSize}`);
  }

  changed = true;
  console.log(`Synced template: ${sourcePath} -> ${targetPath}`);
}

if (!changed) {
  console.log("All templates already current.");
}
