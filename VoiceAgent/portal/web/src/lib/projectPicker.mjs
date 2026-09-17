function normalized(value) {
  return String(value || "").trim().toLowerCase();
}

export function projectDisplayValue(projects, endpoint, fallback = "") {
  const selected = projects.find((project) => project.endpoint === endpoint);
  return selected?.name || fallback || endpoint || "";
}

export function filterProjectsByName(value, projects) {
  const query = normalized(value);
  if (!query) return projects;
  if (query.startsWith("https://")) {
    return projects.filter(
      (project) => normalized(project.endpoint) === query,
    );
  }
  return projects.filter(
    (project) => normalized(project.name).includes(query),
  );
}

export function resolveProjectEndpoint(value, projects) {
  const query = normalized(value);
  if (!query) return "";

  if (
    query.startsWith("https://")
    && query.includes("/api/projects/")
  ) {
    return String(value).trim();
  }

  const matches = filterProjectsByName(value, projects);
  const exact = matches.filter(
    (project) => normalized(project.name) === query,
  );
  if (exact.length === 1) return exact[0].endpoint;
  return matches.length === 1 ? matches[0].endpoint : "";
}
