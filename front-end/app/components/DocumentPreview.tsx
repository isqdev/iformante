"use client";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { PdfViewer } from "./PdfViewer";
import type { PdfCitation } from "./pdf/types";
export type PreviewDocument = {
  id: string;
  name: string;
  source_type: "PDF" | "WEB_PAGE";
  url: string | null;
  citations?: PdfCitation[];
};
export function DocumentPreview({
  document,
  onClose,
  citationTools = true,
}: {
  document: PreviewDocument | null;
  onClose: () => void;
  citationTools?: boolean;
}) {
  return (
    <Dialog
      open={Boolean(document)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className="app-glass-background h-dvh w-screen max-w-none gap-0 rounded-none p-0 sm:max-w-none"
        showCloseButton={false}
      >
        <DialogTitle className="sr-only">
          {document?.name ?? "Visualizador de documento"}
        </DialogTitle>
        <DialogDescription className="sr-only">
          PDF em tela cheia
        </DialogDescription>
        {document?.source_type === "PDF" && (
          <PdfViewer
            key={document.id}
            filename={document.name}
            url={`/api/documents/${encodeURIComponent(document.id)}/content`}
            onClose={onClose}
            fullSize
            citations={document.citations}
            citationTools={citationTools}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
export function DocumentDialogPreview(props: {
  document: PreviewDocument | null;
  onClose: () => void;
}) {
  return <DocumentPreview {...props} citationTools={false} />;
}
