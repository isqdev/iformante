import {backendProxy} from "@/lib/backend-proxy";
type Context = {params: Promise<{documentId: string}>};
async function handle(request: Request, context: Context) {const params = await context.params; return backendProxy(request, `/documents/${encodeURIComponent(params.documentId)}/content`);}
export {handle as GET};
