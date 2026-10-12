"use client";

import { useState } from "react";
import { Pencil, Save } from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { Spinner } from "@/components/ui/spinner";
import { systemRequest, SystemRequestError, type SystemPrompt } from "@/lib/system-client";
import { ParseMarkdown } from "../ParseMarkdown";

export function PromptEditor({ prompt, title, description, draft, onDraft, onSaved, onAccessLost }: {
  prompt: SystemPrompt; title: string; description: string; draft: string | undefined;
  onDraft: (value: string | undefined) => void; onSaved: (prompt: SystemPrompt) => void; onAccessLost: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const editing = draft !== undefined;
  const changed = editing && draft !== prompt.value;

  async function save() {
    if (busy || !changed) return;
    setBusy(true);
    setError("");
    try {
      onSaved(await systemRequest<SystemPrompt>(`prompts/${prompt.param}`, { value: draft, expected_value: prompt.value }));
      onDraft(undefined);
      setConflict(false);
      toast.success("Prompt atualizado com sucesso.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Tente novamente.");
      if (error instanceof SystemRequestError) {
        setConflict(error.status === 409);
        if ([401, 403].includes(error.status)) onAccessLost();
      }
    } finally { setBusy(false); }
  }

  async function reloadSaved() {
    setBusy(true);
    try {
      const prompts = await systemRequest<SystemPrompt[]>("prompts");
      const latest = prompts.find((item) => item.param === prompt.param);
      if (latest) onSaved(latest);
      setConflict(false);
      setError("Versão salva recarregada. Seu rascunho foi preservado; revise antes de salvar.");
    } catch (error) {
      setError(error instanceof Error ? error.message : "Tente novamente.");
      if (error instanceof SystemRequestError && [401, 403].includes(error.status)) onAccessLost();
    } finally { setBusy(false); }
  }

  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader>
      <CardContent>
        {editing ? (
          <Field data-invalid={!!error}>
            <FieldLabel htmlFor={prompt.param} className="sr-only">{title}</FieldLabel>
            <Textarea id={prompt.param} value={draft} onChange={(event) => onDraft(event.target.value)} disabled={busy} maxLength={100000} aria-invalid={!!error} aria-describedby={error ? `${prompt.param}-error` : undefined} className="min-h-80 resize-y" />
          </Field>
        ) : <div className="max-h-[32rem] overflow-auto break-words"><ParseMarkdown content={prompt.value} /></div>}
        {error && <p id={`${prompt.param}-error`} role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
      </CardContent>
      <CardFooter className="flex flex-wrap justify-end gap-2">
        {editing ? <>
          {conflict && <Button variant="outline" disabled={busy} onClick={reloadSaved}>Recarregar versão salva</Button>}
          <Button variant="outline" disabled={busy} onClick={() => { onDraft(undefined); setError(""); setConflict(false); }}>Cancelar</Button>
          <Button disabled={busy || !changed || !draft.trim() || conflict} onClick={save}>{busy ? <Spinner data-icon="inline-start" /> : <Save data-icon="inline-start" />}Salvar</Button>
        </> : <Button variant="outline" onClick={() => onDraft(prompt.value)}><Pencil data-icon="inline-start" />Editar</Button>}
      </CardFooter>
    </Card>
  );
}
