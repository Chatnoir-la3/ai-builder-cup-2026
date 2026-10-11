import { agentFetch } from "@/lib/agent";
import { allow, clientIp } from "@/lib/rate-limit";

export async function POST(request: Request) {
  if (!allow(`reset:${clientIp(request)}`, 10, 10 * 60_000)) {
    return Response.json({ error: "Too many requests. Try again in a few minutes." }, { status: 429 });
  }
  try {
    const res = await agentFetch("/demo/reset", { method: "POST" });
    return Response.json({ ok: res.ok }, { status: res.ok ? 200 : 502 });
  } catch {
    return Response.json({ ok: false }, { status: 502 });
  }
}
