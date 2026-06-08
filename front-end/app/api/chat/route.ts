import {NextResponse} from "next/server";

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const backendUrl = process.env.BACKEND_API_URL ?? DEFAULT_BACKEND_URL;
  const payload = await request.json().catch(() => null);

  if (!payload?.message || typeof payload.message !== "string") {
    return NextResponse.json(
      {error: "Nenhuma mensagem foi enviada."},
      {status: 400},
    );
  }

  let upstreamResponse: Response;

  try {
    upstreamResponse = await fetch(`${backendUrl}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Cookie: request.headers.get("cookie") ?? "",
      },
      body: JSON.stringify({
        conversation_id:
          typeof payload.conversation_id === "string"
            ? payload.conversation_id
            : null,
        message: payload.message,
      }),
    });
  } catch {
    return NextResponse.json(
      {
        error:
          "Nao foi possivel conectar ao back-end FastAPI. Verifique se ele esta em execucao.",
      },
      {status: 502},
    );
  }

  if (!upstreamResponse.ok || !upstreamResponse.body) {
    const contentType = upstreamResponse.headers.get("content-type") ?? "";
    const errorPayload = contentType.includes("application/json")
      ? ((await upstreamResponse.json().catch(() => null)) as
          | {detail?: string; error?: string}
          | null)
      : null;
    const errorText =
      errorPayload?.detail ??
      errorPayload?.error ??
      (await upstreamResponse.text().catch(() => ""));

    return NextResponse.json(
      {
        error: errorText || "Nao foi possivel obter resposta do back-end.",
      },
      {status: upstreamResponse.status || 500},
    );
  }

  const responseHeaders = new Headers({
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
  });
  const setCookie = upstreamResponse.headers.get("set-cookie");

  if (setCookie) {
    responseHeaders.set("Set-Cookie", setCookie);
  }

  return new Response(upstreamResponse.body, {
    headers: responseHeaders,
  });
}
