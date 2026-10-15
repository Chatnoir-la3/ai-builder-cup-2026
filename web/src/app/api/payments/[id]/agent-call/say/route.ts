import { agentFetch } from "@/lib/agent";
import { relayCall } from "@/lib/agent-call";
import { allow, clientIp } from "@/lib/rate-limit";

const MAX_AUDIO = 1_400_000; // base64 of 30 s at 16 kHz, 16-bit
const MAX_TEXT = 500;

// One turn of the payee: recorded speech or typed text. The agent's reply streams back.
export async function POST(request: Request, ctx: RouteContext<"/api/payments/[id]/agent-call/say">) {
  const { id } = await ctx.params;
  if (!allow(`agent-say:${clientIp(request)}`, 60, 10 * 60_000)) {
    return Response.json({ error: "Too many requests. Try again in a few minutes." }, { status: 429 });
  }
  const body = (await request.json().catch(() => null)) as { audio?: unknown; text?: unknown } | null;
  const audio = typeof body?.audio === "string" && body.audio.length <= MAX_AUDIO ? body.audio : undefined;
  const text = typeof body?.text === "string" && body.text.trim() && body.text.length <= MAX_TEXT ? body.text.trim() : undefined;
  if (!audio === !text) return Response.json({ error: "Say something, or type it." }, { status: 400 });
  try {
    const res = await agentFetch(`/demo/payments/${encodeURIComponent(id)}/agent-call/say`, {
      method: "POST",
      body: JSON.stringify(audio ? { audio } : { text }),
    });
    return relayCall(res, "The call dropped. Call the number yourself.");
  } catch {
    return Response.json({ error: "The call dropped. Call the number yourself." }, { status: 502 });
  }
}
