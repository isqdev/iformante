import {NextResponse} from "next/server";

type ChatRequestMessage = {
  content: string;
  role: "assistant" | "user";
};

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const backendUrl = process.env.BACKEND_API_URL ?? DEFAULT_BACKEND_URL;
  const {messages} = (await request.json()) as {messages?: ChatRequestMessage[]};
  const sanitizedMessages = (messages ?? []).filter(
    (message) => message.content.trim().length > 0,
  );

  if (sanitizedMessages.length === 0) {
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
      },
      body: JSON.stringify({messages: sanitizedMessages}),
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
    const errorText = errorPayload?.detail ?? errorPayload?.error ?? (await upstreamResponse.text().catch(() => ""));

    return NextResponse.json(
      {
        error:
          errorText ||
          "Nao foi possivel obter resposta do back-end.",
      },
      {status: upstreamResponse.status || 500},
    );
  }

  return new Response(upstreamResponse.body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
    },
  });
}
