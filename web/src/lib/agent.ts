import { GoogleAuth } from "google-auth-library";

const AGENT_URL = process.env.AGENT_URL ?? "http://127.0.0.1:8080";
const APP_NAME = process.env.AGENT_APP_NAME ?? "app";

type AdkEvent = {
  author?: string;
  content?: { parts?: { text?: string }[] };
};

const auth = new GoogleAuth();

// Cloud Run (https) requires an ID token for service-to-service calls; local dev does not.
async function authHeaders(): Promise<Record<string, string>> {
  if (!AGENT_URL.startsWith("https://")) return {};
  const client = await auth.getIdTokenClient(AGENT_URL);
  const headers = await client.getRequestHeaders();
  const value = headers.get("authorization") ?? headers.get("Authorization");
  return value ? { Authorization: value } : {};
}

export async function runAgent(userId: string, sessionId: string, text: string): Promise<string> {
  const res = await fetch(`${AGENT_URL}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({
      app_name: APP_NAME,
      user_id: userId,
      session_id: sessionId,
      new_message: { role: "user", parts: [{ text }] },
    }),
  });
  if (!res.ok) throw new Error(`agent responded ${res.status}`);
  const events = (await res.json()) as AdkEvent[];
  return events
    .filter((e) => e.author !== "user")
    .flatMap((e) => e.content?.parts ?? [])
    .map((p) => p.text ?? "")
    .join("")
    .trim();
}
