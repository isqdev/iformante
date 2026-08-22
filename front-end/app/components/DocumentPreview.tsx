"use client";

import {Dialog, DialogContent, DialogDescription, DialogTitle} from "@/components/ui/dialog";
import {Sheet, SheetContent, SheetDescription, SheetTitle} from "@/components/ui/sheet";
import {PdfViewer} from "./PdfViewer";

export type PreviewDocument = {id: string; name: string; source_type: "PDF" | "WEB_PAGE"; url: string | null};

export function DocumentPreview({document, onClose}: {document: PreviewDocument | null; onClose: () => void}) {
  return <Sheet open={Boolean(document)} onOpenChange={(open) => { if (!open) onClose(); }}><SheetContent className="w-1/2 min-w-80 gap-0 p-0 sm:w-full sm:max-w-none" showCloseButton={false}><SheetTitle className="sr-only">{document?.name ?? "Visualizador de documento"}</SheetTitle><SheetDescription className="sr-only">Visualizacao do documento armazenado.</SheetDescription>{document?.source_type === "PDF" ? <PdfViewer key={document.id} filename={document.name} url={`/api/documents/${encodeURIComponent(document.id)}/content`} onClose={onClose} /> : null}</SheetContent></Sheet>;
}

export function DocumentDialogPreview({document, onClose}: {document: PreviewDocument | null; onClose: () => void}) {
  return <Dialog open={Boolean(document)} onOpenChange={(open) => { if (!open) onClose(); }}><DialogContent className="h-svh max-w-none gap-0 rounded-none p-0 sm:h-[calc(100svh-2rem)] sm:max-w-[50vw] sm:rounded-xl" showCloseButton={false}><DialogTitle className="sr-only">{document?.name ?? "Visualizador de documento"}</DialogTitle><DialogDescription className="sr-only">Visualizacao do documento armazenado.</DialogDescription>{document?.source_type === "PDF" ? <PdfViewer key={document.id} filename={document.name} url={`/api/documents/${encodeURIComponent(document.id)}/content`} onClose={onClose} /> : null}</DialogContent></Dialog>;
}
