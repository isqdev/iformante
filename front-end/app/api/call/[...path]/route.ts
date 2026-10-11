import { backendProxy } from "@/lib/backend-proxy";

export const runtime = "nodejs";
export const maxDuration = 120;

type Context = { params: Promise<{ path: string[] }> };
const allowed = new Set(["status", "stream", "cancel", "playback"]);

async function proxy(request: Request, context: Context) {
  const { path } = await context.params;
  if (path.length !== 1 || !allowed.has(path[0])) {
    return Response.json({ error: "Rota não encontrada." }, { status: 404 });
  }
  if ((path[0] === "status") !== (request.method === "GET")) {
    return Response.json({ error: "Método inválido." }, { status: 405 });
  }
  return backendProxy(request, `/call/${path[0]}`);
}

export const GET = proxy;
export const POST = proxy;
