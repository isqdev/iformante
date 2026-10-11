import { NextResponse } from "next/server";

export async function backendProxy(request: Request, path: string) {
  const safe = ["GET", "HEAD", "OPTIONS"].includes(request.method);
  const origin = request.headers.get("origin");
  if (!safe && origin && origin !== new URL(request.url).origin) {
    return NextResponse.json({ error: "Origem inválida." }, { status: 403 });
  }
  const headers = new Headers();
  const cookie = request.headers.get("cookie") ?? "";
  headers.set("cookie", cookie);
  const csrf = cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith("iformante_csrf="))
    ?.slice(15);
  if (csrf) headers.set("x-csrf-token", csrf);
  for (const name of ["content-type", "range", "if-range"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const response = await fetch(
      `${process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000"}${path}`,
      {
        method: request.method,
        headers,
        body: safe ? undefined : await request.arrayBuffer(),
        cache: "no-store",
        signal: request.signal,
      },
    );
    const outgoing = new Headers();
    for (const name of [
      "content-type",
      "content-range",
      "accept-ranges",
      "content-disposition",
      "cache-control",
      "x-accel-buffering",
    ]) {
      const value = response.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    outgoing.set("cache-control", "no-store");
    for (const value of response.headers.getSetCookie())
      outgoing.append("set-cookie", value);
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return NextResponse.json(
      { error: "Não foi possível conectar ao servidor." },
      { status: 502 },
    );
  }
}
