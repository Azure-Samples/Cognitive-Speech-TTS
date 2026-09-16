// Copyright (c) Microsoft. All rights reserved.
// Static test fixture only. All API and WebSocket traffic is mocked by studio.spec.mjs.
// This cannot create agents, use Azure credentials, or schedule functional tests.
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve, sep, extname } from "node:path";

const root = fileURLToPath(new URL("../../static/", import.meta.url));
const types = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css", ".png": "image/png" };

createServer(async (request, response) => {
  const path = new URL(request.url, "http://localhost").pathname;
  const relative = path === "/demo/" ? "index.html" : path.startsWith("/static/demo/") ? path.slice(13) : null;
  const filename = relative !== null ? resolve(root, relative) : "";
  if (request.method !== "GET" || !filename.startsWith(root.endsWith(sep) ? root : `${root}${sep}`)) {
    response.writeHead(404).end("No test fixture for this route");
    return;
  }
  try {
    response.writeHead(200, { "Content-Type": types[extname(filename)] || "application/octet-stream" });
    response.end(await readFile(filename));
  } catch {
    response.writeHead(404).end("Fixture asset not found");
  }
}).listen(8098, "127.0.0.1");
