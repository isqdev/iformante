import {backendProxy} from "@/lib/backend-proxy";
type Context = {params: Promise<{path: string[]}>};
async function handle(request: Request, context: Context) {
  const {path} = await context.params;
  return backendProxy(request, `/auth/${path.map(encodeURIComponent).join("/")}`);
}
export {handle as GET, handle as POST, handle as PATCH};
