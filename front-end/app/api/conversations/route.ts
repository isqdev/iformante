import {NextResponse} from "next/server";

const backendUrl = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";

export async function GET(request: Request) {
  try {
    const response = await fetch(`${backendUrl}/conversations`, {
      headers: {
        Cookie: request.headers.get("cookie") ?? "",
      },
      cache: "no-store",
    });

    const payload = await response.json().catch(() => null);
    const nextResponse = NextResponse.json(payload, {status: response.status});
    const setCookie = response.headers.get("set-cookie");

    if (setCookie) {
      nextResponse.headers.set("Set-Cookie", setCookie);
    }

    return nextResponse;
  } catch {
    return NextResponse.json(
      {error: "Nao foi possivel conectar ao back-end."},
      {status: 502},
    );
  }
}
