export function safeApplicationReturnPath(value: string | null): string {
  if (!value || !value.startsWith("/app") || value.startsWith("//")) {
    return "/app/projects";
  }
  return value;
}
