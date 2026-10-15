import { agentFetch } from "@/lib/agent";

export async function POST(_request: Request, ctx: RouteContext<"/api/payments/[id]/agent-call/hang-up">) {
  const { id } = await ctx.params;
  try {
    const res = await agentFetch(`/demo/payments/${encodeURIComponent(id)}/agent-call/hang-up`, { method: "POST" });
    const data = (await res.json().catch(() => ({}))) as { detail?: string };
    if (!res.ok) return Response.json({ error: data.detail ?? "The call was not ended." }, { status: res.status });
    return Response.json(data);
  } catch {
    return Response.json({ error: "The call was not ended." }, { status: 502 });
  }
}
