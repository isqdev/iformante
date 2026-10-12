import { backendProxy } from "@/lib/backend-proxy";

export async function PATCH(request: Request, context: { params: Promise<{ param: string }> }) {
  const { param } = await context.params;
  return backendProxy(request, `/system/prompts/${encodeURIComponent(param)}`);
}
