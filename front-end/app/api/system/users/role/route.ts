import { backendProxy } from "@/lib/backend-proxy";

export async function PATCH(request: Request) {
  return backendProxy(request, "/system/users/role");
}
