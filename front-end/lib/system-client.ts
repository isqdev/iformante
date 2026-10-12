export type PromptKey = "prompt_router" | "prompt_reranker" | "prompt_replier" | "prompt_speech_style" | "prompt_replier_voice" | "prompt_voice_rewrite";
export type SystemPrompt = { id: string; param: PromptKey; value: string };

export class SystemRequestError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function systemRequest<T>(path: string, body?: object): Promise<T> {
  const response = await fetch(`/api/system/${path}`, {
    method: body ? "PATCH" : "GET",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new SystemRequestError(data?.detail ?? data?.error ?? "Não foi possível concluir a solicitação.", response.status);
  return data;
}
