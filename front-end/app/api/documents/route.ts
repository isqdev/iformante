import {NextResponse} from "next/server";

const backendUrl = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";

export async function GET() {
  try {
    const response = await fetch(`${backendUrl}/documents`, {cache: "no-store"});
    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      return NextResponse.json(
        {error: payload?.detail ?? "Não foi possível carregar os documentos."},
        {status: response.status},
      );
    }

    return NextResponse.json(payload);
  } catch {
    return NextResponse.json(
      {error: "Não foi possível conectar ao back-end."},
      {status: 502},
    );
  }
}

export async function POST(request: Request) {
  try {
    const isMultipart = request.headers
      .get("content-type")
      ?.includes("multipart/form-data");
    const response = isMultipart
      ? await fetch(`${backendUrl}/documents/upload`, {
          method: "POST",
          body: await request.formData(),
        })
      : await forwardWebPageRequest(request);

    if (!response.ok) {
      const errorPayload = (await response.json().catch(() => null)) as
        | {detail?: string}
        | null;

      return NextResponse.json(
        {error: errorPayload?.detail ?? "Nao foi possivel processar o documento."},
        {status: response.status},
      );
    }

    return NextResponse.json(await response.json());
  } catch (error) {
    if (error instanceof InvalidRequestError) {
      return NextResponse.json({error: error.message}, {status: 400});
    }
    return NextResponse.json(
      {error: "Nao foi possivel conectar ao back-end."},
      {status: 502},
    );
  }
}

async function forwardWebPageRequest(request: Request) {
  const payload = await request.json().catch(() => null);
  if (!payload?.url || typeof payload.url !== "string") {
    throw new InvalidRequestError("Informe o link da página.");
  }

  return fetch(`${backendUrl}/documents/web-page`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({url: payload.url}),
  });
}

class InvalidRequestError extends Error {}
