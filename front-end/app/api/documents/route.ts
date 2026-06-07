import {NextResponse} from "next/server";

const backendUrl = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";

export async function POST(request: Request) {
  const payload = await request.json().catch(() => null);

  if (!payload?.url || typeof payload.url !== "string") {
    return NextResponse.json(
      {error: "Informe o link do documento."},
      {status: 400},
    );
  }

  try {
    const response = await fetch(`${backendUrl}/documents/download`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({url: payload.url}),
    });

    if (!response.ok) {
      const errorPayload = (await response.json().catch(() => null)) as
        | {detail?: string}
        | null;

      return NextResponse.json(
        {error: errorPayload?.detail ?? "Nao foi possivel baixar o documento."},
        {status: response.status},
      );
    }

    return NextResponse.json(await response.json());
  } catch {
    return NextResponse.json(
      {error: "Nao foi possivel conectar ao back-end."},
      {status: 502},
    );
  }
}
