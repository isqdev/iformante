import {NextResponse} from "next/server";

const backendUrl = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";

type RouteContext = {params: Promise<{documentId: string}>};

export async function DELETE(_request: Request, context: RouteContext) {
  const {documentId} = await context.params;

  try {
    const response = await fetch(`${backendUrl}/documents/${documentId}`, {
      method: "DELETE",
    });
    const payload = await response.json().catch(() => null);

    if (!response.ok) {
      return NextResponse.json(
        {error: payload?.detail ?? "Não foi possível excluir o documento."},
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

export async function PATCH(request: Request, context: RouteContext) {
  const {documentId} = await context.params;
  try {
    const response = await fetch(`${backendUrl}/documents/${documentId}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify(await request.json())});
    const payload = await response.json().catch(() => null);
    if (!response.ok) return NextResponse.json({error: payload?.detail ?? "Não foi possível renomear o documento."}, {status: response.status});
    return NextResponse.json(payload);
  } catch {
    return NextResponse.json({error: "Não foi possível conectar ao back-end."}, {status: 502});
  }
}
