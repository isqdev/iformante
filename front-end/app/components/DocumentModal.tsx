"use client";

import {
  useEffect,
  useRef,
  useState,
  type DragEvent,
  type FormEvent,
} from "react";
import { FileText, Globe, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

import { ifprUrl, type DroppedSource } from "./documents/useDocumentDrop";

type SourceKind = "pdf" | "web-page";

type DocumentModalProps = {
  initialSource?: DroppedSource | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function filenameWithoutExtension(filename: string) {
  return filename.replace(/\.pdf$/i, "");
}

export function DocumentModal({
  open,
  onOpenChange,
  initialSource,
}: DocumentModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [sourceKind, setSourceKind] = useState<SourceKind | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !initialSource) return;
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setSourceKind(initialSource.file ? "pdf" : "web-page");
      setFile(initialSource.file ?? null);
      setUrl(initialSource.url ?? "");
      setTitle(initialSource.title ?? "");
      setError(null);
    });
    if (initialSource.url)
      void fetch("/api/documents/metadata", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: initialSource.url }),
      })
        .then((r) => r.json())
        .then((r) => {
          if (!cancelled && r.title) setTitle(r.title);
        })
        .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [open, initialSource]);

  function resetForm() {
    setSourceKind(null);
    setFile(null);
    setTitle("");
    setUrl("");
    setError(null);
    setIsDragging(false);
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) resetForm();
    onOpenChange(nextOpen);
  }

  function selectPdf(selected: File | undefined) {
    if (!selected) return;
    if (!selected.name.toLowerCase().endsWith(".pdf")) {
      setError("Selecione um arquivo no formato PDF.");
      return;
    }
    setError(null);
    setFile(selected);
    setTitle(filenameWithoutExtension(selected.name));
  }

  function handleDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(false);
    selectPdf(event.dataTransfer.files.item(0) ?? undefined);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (sourceKind === "pdf") {
      if (!file) {
        setError("Selecione um arquivo PDF.");
        return;
      }
      if (!title.trim()) {
        setError("Informe um título para o PDF.");
        return;
      }
    }

    if (sourceKind === "web-page" && !ifprUrl(url.trim())) {
      setError("Informe o link da página do IFPR.");
      return;
    }

    if (!sourceKind) {
      setError("Escolha o tipo de fonte.");
      return;
    }

    setIsSubmitting(true);
    try {
      const response =
        sourceKind === "pdf"
          ? await (() => {
              const formData = new FormData();
              formData.append("file", file!);
              formData.append("title", title.trim());
              return fetch("/api/documents", {
                method: "POST",
                body: formData,
              });
            })()
          : await fetch("/api/documents", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                kind: "web-page",
                url: url.trim(),
                title: title.trim() || undefined,
              }),
            });

      const payload = (await response.json()) as {
        detail?: string;
        error?: string;
      };
      if (!response.ok) {
        throw new Error(
          payload.detail ??
            payload.error ??
            "Não foi possível adicionar a fonte.",
        );
      }

      handleOpenChange(false);
      window.dispatchEvent(new Event("documents:changed"));
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : "Não foi possível adicionar a fonte.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-auto sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Nova fonte</DialogTitle>
            <DialogDescription>
              Envie um PDF ou extraia o conteúdo de uma página do IFPR.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-5 py-5">
            {!sourceKind ? (
              <div
                role="group"
                aria-label="Tipo de fonte"
                className="grid grid-cols-2 gap-3"
              >
                <Button
                  type="button"
                  variant="outline"
                  className="h-28 flex-col gap-2"
                  onClick={() => setSourceKind("pdf")}
                >
                  <FileText className="size-7" />
                  PDF
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="h-28 flex-col gap-2"
                  onClick={() => setSourceKind("web-page")}
                >
                  <Globe className="size-7" />
                  Página Web
                </Button>
              </div>
            ) : sourceKind === "pdf" ? (
              <>
                <Field>
                  <FieldLabel htmlFor="document-file">Arquivo PDF</FieldLabel>
                  <input
                    ref={fileInputRef}
                    id="document-file"
                    type="file"
                    accept="application/pdf,.pdf"
                    className="sr-only"
                    onChange={(event) => selectPdf(event.target.files?.[0])}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="h-32 w-full flex-col gap-2 border-dashed"
                    data-dragging={isDragging || undefined}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(event) => {
                      event.preventDefault();
                      setIsDragging(true);
                    }}
                    onDragLeave={() => setIsDragging(false)}
                    onDrop={handleDrop}
                  >
                    <Upload className="size-6" />
                    <span className="max-w-full truncate">
                      {file
                        ? file.name
                        : "Arraste um PDF ou clique para selecionar"}
                    </span>
                  </Button>
                  <FieldDescription>
                    Arquivos PDF de até 25 MB.
                  </FieldDescription>
                </Field>
                <Field>
                  <FieldLabel htmlFor="document-title">Título</FieldLabel>
                  <Input
                    id="document-title"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    placeholder="Título do documento"
                  />
                  <FieldDescription>
                    Preenchido com o nome do arquivo; você pode editar.
                  </FieldDescription>
                </Field>
              </>
            ) : (
              <>
                <Field>
                  <FieldLabel htmlFor="document-url">Link da página</FieldLabel>
                  <Input
                    id="document-url"
                    type="url"
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                    placeholder="https://ifpr.edu.br/..."
                  />
                  <FieldDescription>
                    Apenas páginas do domínio ifpr.edu.br. O título será
                    extraído da página.
                  </FieldDescription>
                </Field>
                <Field>
                  <FieldLabel htmlFor="web-title">Título (opcional)</FieldLabel>
                  <Input
                    id="web-title"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    maxLength={255}
                  />
                </Field>
              </>
            )}

            {error && <p className="text-sm text-destructive">{error}</p>}
          </div>

          <DialogFooter>
            <DialogClose render={<Button type="button" variant="outline" />}>
              Cancelar
            </DialogClose>
            <Button type="submit" disabled={!sourceKind || isSubmitting}>
              {isSubmitting ? "Adicionando..." : "Adicionar fonte"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
