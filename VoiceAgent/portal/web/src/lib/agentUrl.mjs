// Copyright (c) Microsoft. All rights reserved.

export function withSelectedAgent(href, agentName) {
  const url = new URL(href);
  const selected = String(agentName || "").trim();
  if (selected) url.searchParams.set("agent", selected);
  else url.searchParams.delete("agent");
  return url.toString();
}
