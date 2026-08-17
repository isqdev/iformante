const backendUrl = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";

type RouteContext = {params: Promise<{documentId: string}>};

const FORWARDED_HEADERS = [
  "accept-ranges",
  "content-disposition",
  "content-length",
  "content-range",
  "content-type",
  "etag",
  "last-modified",
] as const;

export async function GET(request: Request, context: RouteContext) {
  const {documentId} = await context.params;
  const range = request.headers.get("range");

  try {
    const response = await fetch(
      `${backendUrl}/documents/${encodeURIComponent(documentId)}/content`,
      {
        cache: "no-store",
        headers: range ? {Range: range} : undefined,
      },
    );
    const headers = new Headers();

    for (const name of FORWARDED_HEADERS) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }

    return new Response(response.body, {
      status: response.status,
      headers,
    });
  } catch {
    return Response.json(
      {error: "Nao foi possivel carregar o PDF armazenado."},
      {status: 502},
    );
  }
}
