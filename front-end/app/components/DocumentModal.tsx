"use client";

import {MouseEvent, SyntheticEvent, useState} from "react";
import {Button, Input, Modal, Spinner, Toast, type UseOverlayStateReturn} from "@heroui/react";

type DocumentModalProps = {
  state: UseOverlayStateReturn;
};

export function DocumentModal({state}: DocumentModalProps) {
  const [documentUrl, setDocumentUrl] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedUrl = documentUrl.trim();

    if (!trimmedUrl || isSubmitting) {
      return;
    }

    setDocumentUrl("");
    setIsSubmitting(true);

    try {
      const response = await fetch("/api/documents", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({url: trimmedUrl}),
      });

      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as
          | {error?: string}
          | null;

        throw new Error(payload?.error ?? "Nao foi possivel baixar o documento.");
      }

      state.close();
      Toast.toast.success("Documento baixado com sucesso.");
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Nao foi possivel baixar o documento.";

      Toast.toast.danger(message);
    } finally {
      setIsSubmitting(false);
    }
  }

  function stopModalClickPropagation(event: MouseEvent) {
    event.stopPropagation();
  }

  return (
    <Modal state={state}>
      <Modal.Backdrop className="bg-backdrop" isDismissable onClick={state.close}>
        <Modal.Container className="flex min-h-screen items-center justify-center p-4" placement="center">
          <Modal.Dialog
            className="relative w-[min(92vw,36rem)] rounded-2xl bg-overlay p-6 shadow-overlay"
            onClick={stopModalClickPropagation}
          >
            <Modal.CloseTrigger className="absolute right-4 top-4" />

            <Modal.Header>
              <Modal.Heading>Adicionar link do novo documento</Modal.Heading>
            </Modal.Header>

            <form className="mt-5 flex items-center gap-3" onSubmit={handleSubmit}>
              <Input
                aria-label="Link do documento"
                className="min-w-0 flex-1"
                disabled={isSubmitting}
                placeholder="Link do documento"
                type="url"
                value={documentUrl}
                variant="primary"
                onChange={(event) => setDocumentUrl(event.target.value)}
              />

              <Button
                className="shrink-0"
                isDisabled={documentUrl.trim().length === 0 || isSubmitting}
                type="submit"
                variant="primary"
              >
                Enviar
              </Button>
            </form>

            {isSubmitting ? (
              <div className="mt-5 flex justify-center">
                <Spinner aria-label="Baixando documento" color="accent" size="sm" />
              </div>
            ) : null}
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  );
}
