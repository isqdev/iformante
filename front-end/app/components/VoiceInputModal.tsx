"use client";

import {useEffect} from "react";
import {Button, Modal, type UseOverlayStateReturn} from "@heroui/react";
import {Microphone, Xmark} from "@gravity-ui/icons";

type VoiceInputModalProps = {
  isListening: boolean;
  onCancel: () => void;
  state: UseOverlayStateReturn;
  transcript: string;
};

export function VoiceInputModal({
  isListening,
  onCancel,
  state,
  transcript,
}: VoiceInputModalProps) {
  useEffect(() => {
    if (!state.isOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onCancel, state.isOpen]);

  return (
    <Modal state={state}>
      <Modal.Backdrop className="bg-background" isDismissable={false}>
        <Modal.Container className="h-screen w-screen p-0" placement="center">
          <Modal.Dialog className="relative flex h-screen w-screen max-w-none items-center justify-center rounded-none bg-background">
            <Modal.Header className="sr-only">
              <Modal.Heading>Entrada por voz</Modal.Heading>
            </Modal.Header>

            <Button
              isIconOnly
              aria-label="Cancelar entrada por voz"
              className="absolute right-6 top-6"
              size="lg"
              variant="ghost"
              onPress={onCancel}
            >
              <Xmark className="h-6 w-6" />
            </Button>

            <div className="flex w-full max-w-3xl flex-col items-center gap-8 px-6 text-center">
              <Microphone
                aria-hidden="true"
                className={
                  "h-16 w-16 " + (isListening ? "animate-pulse" : "opacity-60")
                }
              />

              <p
                aria-live="polite"
                className="min-h-16 text-2xl leading-relaxed"
              >
                {transcript || "Pode falar..."}
              </p>
            </div>
          </Modal.Dialog>
        </Modal.Container>
      </Modal.Backdrop>
    </Modal>
  );
}
