import {backendProxy} from "@/lib/backend-proxy";
type Context = {params: Promise<{conversationId: string}>};
async function handle(request: Request, context: Context) {const params = await context.params; return backendProxy(request, `/conversations/${encodeURIComponent(params.conversationId)}`);}
export {handle as GET};
