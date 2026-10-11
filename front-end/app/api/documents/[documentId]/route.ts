import {backendProxy} from "@/lib/backend-proxy";
type Context = {params: Promise<{documentId: string}>};
async function handle(request: Request, context: Context) {const params = await context.params; return backendProxy(request, `/documents/${encodeURIComponent(params.documentId)}`);}
export {handle as GET, handle as PATCH, handle as DELETE};
