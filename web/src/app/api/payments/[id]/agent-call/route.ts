import { agentFetch } from "@/lib/agent";
import { relayCall } from "@/lib/agent-call";
import { allow, clientIp } from "@/lib/rate-limit";

// Places the verification call; the agent's greeting streams back as it is spoken.
export async function POST(request: Request, ctx: RouteContext<"/api/payments/[id]/agent-call">) {
  const { id } = await ctx.params;
  if (!allow(`agent-call:${clientIp(request)}`, 10, 10 * 60_000)) {
    return Response.json({ error: "Too many calls. Try again in a few minutes." }, { status: 429 });
  }
  try {
    const res = await agentFetch(`/demo/payments/${encodeURIComponent(id)}/agent-call`, { method: "POST" });
    return relayCall(res, "The call could not be placed.");
  } catch {
    return Response.json({ error: "The call could not be placed." }, { status: 502 });
  }
}
