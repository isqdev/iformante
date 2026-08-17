"use client";

import {SyntheticEvent, useState} from "react";
import {toast} from "sonner";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {Field, FieldGroup, FieldLabel} from "@/components/ui/field";
import {Input} from "@/components/ui/input";
import {Spinner} from "@/components/ui/spinner";

type DocumentModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function DocumentModal({open, onOpenChange}: DocumentModalProps) {
  const [documentUrl, setDocumentUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedUrl = documentUrl.trim();

    if (!trimmedUrl || isSubmitting) return;

    setIsSubmitting(true);

    try {
      const response = await fetch("/api/documents", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url: trimmedUrl}),
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | {error?: string}
          | null;
        throw new Error(
          payload?.error ?? "Não foi possível processar o documento.",
        );
      }

      setDocumentUrl("");
      onOpenChange(false);
      toast.success("Documento enviado com sucesso.");
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Não foi possível processar o documento.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Adicionar novo documento</DialogTitle>
          <DialogDescription>
            Informe o link do documento que será processado.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="document-url">Link do documento</FieldLabel>
              <Input
                id="document-url"
                disabled={isSubmitting}
                placeholder="https://..."
                type="url"
                value={documentUrl}
                onChange={(event) => setDocumentUrl(event.target.value)}
              />
            </Field>
            <Field orientation="horizontal" className="justify-end">
              <Button
                disabled={documentUrl.trim().length === 0 || isSubmitting}
                type="submit"
              >
                {isSubmitting ? <Spinner data-icon="inline-start" /> : null}
                Enviar
              </Button>
            </Field>
          </FieldGroup>
        </form>
      </DialogContent>
    </Dialog>
  );
}
