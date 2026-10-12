import { agentFetch } from "@/lib/agent";
import { allow, clientIp } from "@/lib/rate-limit";

export async function POST(request: Request, ctx: RouteContext<"/api/payments/[id]/decision">) {
  const { id } = await ctx.params;
  if (!allow(`decision:${clientIp(request)}`, 60, 10 * 60_000)) {
    return Response.json({ error: "Too many requests. Try again in a few minutes." }, { status: 429 });
  }
  const body = (await request.json().catch(() => null)) as { decision?: unknown; approver?: unknown } | null;
  const decision = body?.decision;
  if (decision !== "approved" && decision !== "held") {
    return Response.json({ error: "invalid request" }, { status: 400 });
  }
  try {
    const res = await agentFetch(`/demo/payments/${encodeURIComponent(id)}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, approver: typeof body?.approver === "string" ? body.approver : null }),
    });
    const data = (await res.json().catch(() => ({}))) as { detail?: string };
    if (!res.ok) return Response.json({ error: data.detail ?? "The decision was not saved." }, { status: res.status });
    return Response.json(data);
  } catch {
    return Response.json({ error: "The decision was not saved." }, { status: 502 });
  }
}
