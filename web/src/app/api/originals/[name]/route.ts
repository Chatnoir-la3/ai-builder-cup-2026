import { agentFetch } from "@/lib/agent";

export async function GET(_request: Request, ctx: RouteContext<"/api/originals/[name]">) {
  const { name } = await ctx.params;
  if (!/^[\w.-]+\.(png|jpg|jpeg)$/.test(name)) return new Response("Not found", { status: 404 });
  try {
    const res = await agentFetch(`/demo/originals/${encodeURIComponent(name)}`);
    if (!res.ok) return new Response("Not found", { status: 404 });
    return new Response(res.body, {
      headers: { "Content-Type": res.headers.get("Content-Type") ?? "image/png", "Cache-Control": "private, max-age=300" },
    });
  } catch {
    return new Response("Unavailable", { status: 502 });
  }
}
