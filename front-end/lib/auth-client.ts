export async function authRequest<T = { message: string }>(
  path: string,
  body?: object,
  method = "POST",
): Promise<T> {
  const response = await fetch(`/api/auth/${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      data?.detail ?? data?.error ?? "Não foi possível concluir a solicitação.",
    );
  return data;
}

export function completeInstitutionalEmail(value: string) {
  const match = value.match(/^([^@]{3,})@$/);
  if (!match) return value;
  if (/^[0-9]/.test(match[1])) return `${value}estudantes.ifpr.edu.br`;
  if (/^[a-z]/i.test(match[1])) return `${value}ifpr.edu.br`;
  return value;
}
