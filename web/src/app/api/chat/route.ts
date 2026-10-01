import { runAgent } from "@/lib/agent";

const MAX_LEN = 4000;

export async function POST(request: Request) {
  const body = (await request.json().catch(() => null)) as { sessionId?: unknown; text?: unknown } | null;
  const text = typeof body?.text === "string" ? body.text.trim() : "";
  const sessionId = typeof body?.sessionId === "string" ? body.sessionId : "";
  if (!text || text.length > MAX_LEN || !/^[\w-]{8,64}$/.test(sessionId)) {
    return Response.json({ error: "invalid request" }, { status: 400 });
  }
  try {
    const reply = await runAgent("demo-user", sessionId, text);
    return Response.json({ reply });
  } catch {
    return Response.json({ error: "agent unavailable" }, { status: 502 });
  }
}
