import { backendProxy } from "@/lib/backend-proxy";

export async function GET(request: Request) {
  return backendProxy(request, "/system/prompts");
}
