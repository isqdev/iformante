"use client";

import {Microphone, Xmark} from "@gravity-ui/icons";
import {Button} from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type VoiceInputModalProps = {
  isListening: boolean;
  onCancel: () => void;
  open: boolean;
  transcript: string;
};

export function VoiceInputModal({
  isListening,
  onCancel,
  open,
  transcript,
}: VoiceInputModalProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onCancel();
      }}
    >
      <DialogContent
        className="flex h-svh max-h-none w-screen max-w-none items-center justify-center rounded-none"
        showCloseButton={false}
      >
        <DialogHeader className="sr-only">
          <DialogTitle>Entrada por voz</DialogTitle>
          <DialogDescription>
            Fale sua pergunta ou cancele a gravação.
          </DialogDescription>
        </DialogHeader>

        <Button
          aria-label="Cancelar entrada por voz"
          className="absolute right-6 top-6"
          size="icon-lg"
          variant="ghost"
          onClick={onCancel}
        >
          <Xmark />
        </Button>

        <div className="flex w-full max-w-3xl flex-col items-center gap-8 px-6 text-center">
          <Microphone
            aria-hidden="true"
            className={isListening ? "size-16 animate-pulse" : "size-16 opacity-60"}
          />
          <p aria-live="polite" className="min-h-16 text-2xl leading-relaxed">
            {transcript || "Pode falar..."}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
