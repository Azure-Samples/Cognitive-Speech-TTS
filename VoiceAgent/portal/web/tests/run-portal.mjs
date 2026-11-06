// Copyright (c) Microsoft. All rights reserved.
// Launch the Foundry-only portal with test-only substitutes at Azure boundaries.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("../../", import.meta.url));
const venv = join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.VOICE_PORTAL_PYTHON || (existsSync(venv) ? venv : "python");
const child = spawn(python, ["-u", "tests/serve_portal.py"], {
  cwd: root,
  stdio: "inherit",
  windowsHide: true,
  env: { ...process.env, PYTHON_DOTENV_DISABLED: "1", AZURE_VOICE_AGENTS_ENDPOINT: "" },
});
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("error", (error) => { console.error(error.message); process.exit(1); });
child.on("exit", (code) => process.exit(code ?? 0));
