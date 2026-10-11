import {backendProxy} from "@/lib/backend-proxy";
export async function GET(request: Request) {return backendProxy(request, "/documents");}
export async function POST(request: Request) {return backendProxy(request, request.headers.get("content-type")?.includes("multipart/form-data") ? "/documents/upload" : "/documents/web-page");}
