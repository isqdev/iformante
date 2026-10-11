import {backendProxy} from "@/lib/backend-proxy";
export async function POST(request: Request) {return backendProxy(request, "/chat/stream");}
