"use client";

import { useState } from "react";
import { Mic, PhoneOff, FileText, Volume2 } from "lucide-react";
import { TailChase } from "ldrs/react";
import "ldrs/react/TailChase.css";
import { Button } from "@/components/ui/button";
import { useCall, type CallState } from "../../hooks/useCall";
import { PageContainer } from "../PageContainer";
import { ChatHeader } from "../ChatHeader";
import { InformanteAvatar } from "./InformanteAvatar";
import { DocumentDialogPreview, type PreviewDocument } from "../DocumentPreview";
import type { MessageSource } from "../../models/message";

const labels: Record<CallState, string> = {
  off: "", starting: "Preparando o microfone…", ready: "Pronto para ouvir",
  recording: "Estou ouvindo…", transcribing: "Entendendo sua pergunta…", thinking: "Preparando a resposta…", speaking: "InFormante está falando…",
};

export function CallPage() {
  const call = useCall();
  const [preview, setPreview] = useState<PreviewDocument | null>(null);
  const enabled = call.state !== "off" && call.state !== "starting";
  const busy = call.state === "transcribing" || call.state === "thinking";
  const lastAnswer = call.messages.findLast((m) => m.role === "assistant");
  const idle = call.state === "off";
  const hint = call.hint || call.configurationHint;

  function openSource(source: MessageSource) {
    // Match /docs: PDFs use the fullscreen viewer; web sources open their URL.
    if (source.source_type === "WEB_PAGE" && source.url) {
      window.open(source.url, "_blank", "noopener,noreferrer");
      return;
    }
    setPreview({ id: source.document_id, name: source.filename, source_type: "PDF", url: source.url, citations: source.citations });
  }

  return (
    <PageContainer>
      <ChatHeader title="Chamada" />
      <main className="call-page flex min-h-0 flex-1 flex-col overflow-y-auto" data-state={call.state}>
        <div className="mx-auto flex min-h-min w-full max-w-[1180px] flex-1 items-center justify-center p-5 md:p-8">
          <section className="call-stage flex w-full min-w-0 flex-col items-center justify-center gap-5 text-center" aria-label="Conversa por voz com o InFormante">
            <div className="call-avatar-stage relative flex w-full max-w-md items-center justify-center">
              <div className="call-avatar-halo" aria-hidden="true" />
              <InformanteAvatar state={call.state} player={call.player} />
            </div>
            <div className="flex flex-col items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight md:text-3xl">Fale com o InFormante</h1>
              {!idle && <div className="flex min-h-6 items-center gap-2 text-sm text-muted-foreground" role="status" aria-live="polite">
                {(busy || call.state === "starting") && <div className="flex shrink-0" role="img" aria-label="Gerando resposta"><TailChase size="20" speed="1.75" color="var(--foreground)" /></div>}
                {call.state === "speaking" && <Volume2 className="size-4" />}
                {call.state === "recording" && <Mic className="size-4" />}
                <span>{labels[call.state]}</span>
              </div>}
            </div>
            <div className="flex w-full max-w-sm flex-col items-center gap-3">
              {idle || call.state === "starting" ? (
                <Button size="lg" className="h-14 w-full rounded-full" disabled={call.checking || !call.available || call.state === "starting"} onClick={() => void call.enable()}>
                  <Mic data-icon="inline-start" />
                  {call.checking ? "Verificando chamada…" : call.state === "starting" ? "Preparando chamada…" : call.hint ? "Tentar novamente" : "Retomar chamada"}
                </Button>
              ) : (
                <Button size="lg" className="h-14 w-full touch-none rounded-full" variant={call.state === "recording" ? "recording" : "default"} data-call-talk="true" data-testid="call-talk" aria-label="Segure para falar" aria-pressed={call.state === "recording"} aria-keyshortcuts="Space" disabled={busy || call.state === "speaking"}
                  onPointerDown={(event) => { if (event.button !== 0) return; event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); call.press("pointer"); }}
                  onPointerUp={(event) => { call.release("pointer"); if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}
                  onPointerCancel={() => call.release("pointer", true)}
                  onLostPointerCapture={() => call.release("pointer", true)}
                  onContextMenu={(event) => event.preventDefault()}
                  onClick={(event) => event.preventDefault()}>
                  <Mic data-icon="inline-start" />
                  {call.state === "recording" ? "Solte para enviar" : "Segure para falar"}
                </Button>
              )}
              <p className="text-xs leading-relaxed text-muted-foreground">{enabled ? "Segure espaço ou o botão. Solte para enviar." : "Permita o acesso ao microfone para conversar."}</p>
              {!!hint && <p className="text-sm leading-relaxed text-foreground" role="status" aria-live="polite">{hint}</p>}
              {enabled && <Button variant="destructive" onClick={call.disable}><PhoneOff data-icon="inline-start" />Encerrar chamada</Button>}
            </div>
            {!!lastAnswer?.sources?.length && <nav className="flex max-w-md flex-wrap justify-center gap-2" aria-label="Fontes da resposta">{lastAnswer.sources.map((source) => <Button key={source.document_id} size="sm" variant="source" onClick={() => openSource(source)}><FileText data-icon="inline-start" /><span className="max-w-48 truncate">{source.filename}</span></Button>)}</nav>}
          </section>
        </div>
      </main>
      <DocumentDialogPreview document={preview} onClose={() => setPreview(null)} />
    </PageContainer>
  );
}
