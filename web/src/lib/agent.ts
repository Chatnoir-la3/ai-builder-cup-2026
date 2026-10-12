import { GoogleAuth } from "google-auth-library";

const AGENT_URL = process.env.AGENT_URL ?? "http://127.0.0.1:8080";

const auth = new GoogleAuth();

// Cloud Run (https) requires an ID token for service-to-service calls; local dev does not.
async function authHeaders(): Promise<Record<string, string>> {
  if (!AGENT_URL.startsWith("https://")) return {};
  const client = await auth.getIdTokenClient(AGENT_URL);
  const headers = await client.getRequestHeaders();
  const value = headers.get("authorization") ?? headers.get("Authorization");
  return value ? { Authorization: value } : {};
}

export async function agentFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = { ...(init.body ? { "Content-Type": "application/json" } : {}), ...(await authHeaders()) };
  return fetch(`${AGENT_URL}${path}`, { ...init, headers: { ...headers, ...init.headers }, cache: "no-store" });
}

