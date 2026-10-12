"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldPlus, ShieldMinus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { systemRequest, SystemRequestError, type PromptKey, type SystemPrompt } from "@/lib/system-client";
import { useAuth } from "../auth/AuthProvider";
import { PageContainer } from "../PageContainer";
import { PromptEditor } from "./PromptEditor";
import { RoleDialog } from "./RoleDialog";

const editors: { key: PromptKey; title: string; description: string; group: string }[] = [
  { key: "prompt_router", title: "Router", description: "Decide como processar cada mensagem e quando buscar documentos.", group: "router" },
  { key: "prompt_reranker", title: "ReRanker", description: "Ordena os trechos encontrados pela relevância para a pergunta.", group: "reranker" },
  { key: "prompt_replier", title: "Resposta de texto", description: "Orienta as respostas do chat a partir dos documentos encontrados.", group: "replier" },
  { key: "prompt_speech_style", title: "Estilo de voz", description: "Define a apresentação falada. Mantenha {{max_words}} para incluir a orientação de tamanho; ultrapassar esse valor não bloqueia a resposta.", group: "replier" },
  { key: "prompt_replier_voice", title: "Resposta de voz", description: "Orienta as respostas da chamada a partir dos documentos. Mantenha {{speech_style}} para aplicar o estilo de voz.", group: "replier" },
  { key: "prompt_voice_rewrite", title: "Adaptação para voz", description: "Adapta as respostas diretas do Router para fala. Mantenha {{speech_style}}. Cada resposta é gerada uma única vez.", group: "replier" },
];

export function SystemPage() {
  const { user, loading: authLoading, refresh } = useAuth();
  const router = useRouter();
  const [prompts, setPrompts] = useState<SystemPrompt[]>([]);
  const [drafts, setDrafts] = useState<Partial<Record<PromptKey, string>>>({});
  const [group, setGroup] = useState("router");
  const [role, setRole] = useState<"ADMIN" | "SUPER" | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [accessLost, setAccessLost] = useState(false);
  const allowed = user?.role === "SUPER" && !accessLost;
  const dirty = prompts.some((prompt) => drafts[prompt.param] !== undefined && drafts[prompt.param] !== prompt.value);
  const onAccessLost = useCallback(() => { setAccessLost(true); setRole(null); void refresh(); }, [refresh]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try { setPrompts(await systemRequest<SystemPrompt[]>("prompts")); }
    catch (error) {
      setError(error instanceof Error ? error.message : "Tente novamente.");
      if (error instanceof SystemRequestError && [401, 403].includes(error.status)) onAccessLost();
    } finally { setLoading(false); }
  }, [onAccessLost]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);
  useEffect(() => {
    let active = true;
    if (allowed) queueMicrotask(() => { if (active) void load(); });
    return () => { active = false; };
  }, [allowed, load]);
  useEffect(() => {
    if (!dirty) return;
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    const beforeNavigate = (event: Event) => { if (!window.confirm("Há alterações não salvas nos prompts. Deseja sair e descartá-las?")) event.preventDefault(); };
    window.addEventListener("beforeunload", beforeUnload);
    window.addEventListener("system:before-navigate", beforeNavigate);
    return () => { window.removeEventListener("beforeunload", beforeUnload); window.removeEventListener("system:before-navigate", beforeNavigate); };
  }, [dirty]);

  return (
    <PageContainer>
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b p-4">
        <div className="flex items-center gap-3"><SidebarTrigger /><h1 className="text-lg font-semibold">Sistema</h1></div>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
        {authLoading ? <p role="status">Verificando acesso…</p> : !allowed ? <p role="alert">Acesso exclusivo para SUPER.</p> : (
          <div className="mx-auto flex max-w-5xl flex-col gap-5">
            <section aria-labelledby="user-level-title" className="flex flex-col gap-3">
              <header><h2 id="user-level-title" className="text-xl font-semibold">Nível Usuário</h2></header>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" onClick={() => setRole("ADMIN")}><ShieldMinus data-icon="inline-start" />Rebaixar</Button>
                <Button onClick={() => setRole("SUPER")}><ShieldPlus data-icon="inline-start" />Promover</Button>
              </div>
            </section>
            <section aria-labelledby="prompt-hub-title" className="flex flex-col gap-5">
            <h2 id="prompt-hub-title" className="text-xl font-semibold">Prompt Hub</h2>
            <ToggleGroup aria-label="Selecionar grupo de prompts" variant="outline" value={[group]} onValueChange={(values) => { if (values.length) setGroup(values[0]); }}>
              <ToggleGroupItem value="router">Router</ToggleGroupItem><ToggleGroupItem value="reranker">ReRanker</ToggleGroupItem><ToggleGroupItem value="replier">Replier</ToggleGroupItem>
            </ToggleGroup>
            {loading ? <div role="status" aria-label="Carregando prompts"><Skeleton className="h-80 w-full" /></div> : error ? <div className="flex flex-col items-start gap-3"><p role="alert">{error}</p><Button variant="outline" onClick={load}>Tentar novamente</Button></div> : editors.map((editor) => {
              const prompt = prompts.find((item) => item.param === editor.key);
              return prompt && <div key={editor.key} hidden={editor.group !== group}>
                <PromptEditor prompt={prompt} title={editor.title} description={editor.description} draft={drafts[prompt.param]} onDraft={(value) => setDrafts((current) => ({ ...current, [prompt.param]: value }))} onSaved={(updated) => setPrompts((current) => current.map((item) => item.param === updated.param ? updated : item))} onAccessLost={onAccessLost} />
              </div>;
            })}
            </section>
          </div>
        )}
      </main>
      {allowed && role && <RoleDialog key={role} role={role} onClose={() => setRole(null)} onAccessLost={onAccessLost} />}
    </PageContainer>
  );
}
