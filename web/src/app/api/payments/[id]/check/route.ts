import { agentFetch } from "@/lib/agent";
import { allow, clientIp } from "@/lib/rate-limit";

export async function POST(request: Request, ctx: RouteContext<"/api/payments/[id]/check">) {
  const { id } = await ctx.params;
  if (!allow(`check:${clientIp(request)}`, 30, 10 * 60_000)) {
    return Response.json({ error: "Too many checks. Try again in a few minutes." }, { status: 429 });
  }
  try {
    const res = await agentFetch("/check", { method: "POST", body: JSON.stringify({ payment_id: id }) });
    if (res.status === 404) return Response.json({ error: "Unknown payment." }, { status: 404 });
    if (!res.ok) return Response.json({ error: "The check could not run." }, { status: 502 });
    return Response.json(await res.json());
  } catch {
    return Response.json({ error: "The check could not run." }, { status: 502 });
  }
}
