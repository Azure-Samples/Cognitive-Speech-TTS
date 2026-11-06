import test from "node:test";
import assert from "node:assert/strict";
import {
  filterProjectsByName,
  projectDisplayValue,
  resolveProjectEndpoint,
} from "./projectPicker.mjs";

const projects = [
  {
    name: "voice-agent-india-tip",
    account: "account-one",
    label: "voice-agent-india-tip · account-one",
    endpoint: "https://account-one.services.ai.azure.com/api/projects/voice-agent-india-tip",
  },
  {
    name: "voice-agent-sandbox",
    account: "account-two",
    label: "voice-agent-sandbox · account-two",
    endpoint: "https://account-two.services.ai.azure.com/api/projects/voice-agent-sandbox",
  },
  {
    name: "voice-agent-sandbox-copy",
    account: "account-two",
    label: "voice-agent-sandbox-copy · account-two",
    endpoint: "https://account-two.services.ai.azure.com/api/projects/voice-agent-sandbox-copy",
  },
];

test("displays only the selected project name", () => {
  assert.equal(
    projectDisplayValue(projects, projects[0].endpoint, "fallback"),
    projects[0].name,
  );
  assert.equal(projectDisplayValue([], "", "current-project"), "current-project");
});

test("resolves an exact project name case-insensitively", () => {
  assert.equal(
    resolveProjectEndpoint("VOICE-AGENT-INDIA-TIP", projects),
    projects[0].endpoint,
  );
});

test("does not search account names or endpoint resource text", () => {
  assert.equal(resolveProjectEndpoint("account-one", projects), "");
  assert.equal(
    resolveProjectEndpoint("account-two.services.ai.azure.com", projects),
    "",
  );
});

test("filters suggestions only by project name", () => {
  assert.deepEqual(
    filterProjectsByName("india-tip", projects).map((project) => project.name),
    ["voice-agent-india-tip"],
  );
  assert.deepEqual(filterProjectsByName("account-two", projects), []);
});

test("accepts a pasted project endpoint not present in discovery results", () => {
  const endpoint = "https://new-account.services.ai.azure.com/api/projects/new-project";
  assert.equal(resolveProjectEndpoint(endpoint, projects), endpoint);
});

test("resolves only a unique partial match", () => {
  assert.equal(
    resolveProjectEndpoint("india-tip", projects),
    projects[0].endpoint,
  );
  assert.equal(resolveProjectEndpoint("sandbox", projects), "");
  assert.equal(resolveProjectEndpoint("", projects), "");
});

test("does not guess when the same project name exists in two accounts", () => {
  const duplicate = {
    ...projects[0],
    account: "account-three",
    label: "voice-agent-india-tip · account-three",
    endpoint: "https://account-three.services.ai.azure.com/api/projects/voice-agent-india-tip",
  };
  assert.equal(
    resolveProjectEndpoint("voice-agent-india-tip", [...projects, duplicate]),
    "",
  );
  assert.deepEqual(
    filterProjectsByName(
      "voice-agent-india-tip",
      [...projects, duplicate],
    ).map((project) => project.endpoint),
    [projects[0].endpoint, duplicate.endpoint],
  );
});
