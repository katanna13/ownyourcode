export class AuthenticationRequestError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AuthenticationRequestError";
  }
}

type AuthenticatedFetchOptions = RequestInit & {
  getToken: () => Promise<string | null>;
  onUnauthorized: () => void;
};

export async function authenticatedFetch(
  input: string,
  { getToken, onUnauthorized, headers, ...options }: AuthenticatedFetchOptions
): Promise<Response> {
  const token = await getToken();
  if (!token) {
    onUnauthorized();
    throw new AuthenticationRequestError("Authentication is required.");
  }

  const requestHeaders = new Headers(headers);
  requestHeaders.set("Authorization", `Bearer ${token}`);
  const response = await fetch(input, { ...options, headers: requestHeaders });
  if (response.status === 401) {
    onUnauthorized();
  }
  return response;
}

export function apiBaseUrl(): string | null {
  return import.meta.env.VITE_API_BASE_URL?.replace(/\/+$/, "") || null;
}

export function responseMessages(payload: unknown): string[] {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return [];
  }
  const { detail } = payload;
  if (typeof detail === "string") {
    return [detail];
  }
  if (!Array.isArray(detail)) {
    return [];
  }
  return detail.flatMap((issue) => (
    typeof issue === "object" && issue !== null && "msg" in issue && typeof issue.msg === "string"
      ? [issue.msg]
      : []
  ));
}
