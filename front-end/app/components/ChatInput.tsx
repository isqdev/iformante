"use client";

import {useEffect, useRef, useState} from "react";
import {toast} from "sonner";
import {Microphone, PaperPlane, Xmark} from "@gravity-ui/icons";
import {Button} from "@/components/ui/button";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import {useSpeechRecognition} from "../hooks/useSpeechRecognition";
import {AudioVisualizer} from "./AudioVisualizer";

type ChatInputProps = {
  canSend: boolean;
  draft: string;
  focusKey: string;
  isStreaming?: boolean;
  onDraftChange: (value: string) => void;
  onSend: (message?: string) => void;
};

export function ChatInput({
  canSend,
  draft,
  focusKey,
  isStreaming = false,
  onDraftChange,
  onSend,
}: ChatInputProps) {
  const composerRef = useRef<HTMLDivElement>(null);
  const [isVoiceInputActive, setIsVoiceInputActive] = useState(false);
  const hasDraft = draft.trim().length > 0;
  const speechRecognition = useSpeechRecognition({
    onError: (message) => {
      setIsVoiceInputActive(false);
      toast.error(message);
      focusInput();
    },
    onFinalTranscript: (transcript) => {
      setIsVoiceInputActive(false);
      onSend(transcript);
      focusInput();
    },
  });

  function focusInput() {
    requestAnimationFrame(() => {
      composerRef.current?.querySelector("textarea")?.focus();
    });
  }

  function handleSend() {
    if (!canSend || isStreaming) {
      return;
    }

    onSend(draft);
    focusInput();
  }

  function handleStartVoiceInput() {
    if (isStreaming || !speechRecognition.isSupported) {
      return;
    }

    if (!speechRecognition.start()) {
      setIsVoiceInputActive(false);
      return;
    }

    setIsVoiceInputActive(true);
  }

  function handleCancelVoiceInput() {
    speechRecognition.cancel();
    setIsVoiceInputActive(false);
    focusInput();
  }

  function handleSubmitVoiceInput() {
    if (!speechRecognition.submit()) {
      toast.info("Fale antes de enviar o áudio.");
    }
  }

  useEffect(() => {
    focusInput();
  }, [focusKey]);

  useEffect(() => {
    function handleVoiceShortcut(event: KeyboardEvent) {
      if (
        event.key.toLowerCase() !== "m" ||
        event.altKey ||
        !event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        event.repeat ||
        isVoiceInputActive ||
        isStreaming ||
        !speechRecognition.isSupported
      ) {
        return;
      }

      event.preventDefault();
      handleStartVoiceInput();
    }

    window.addEventListener("keydown", handleVoiceShortcut);
    return () => window.removeEventListener("keydown", handleVoiceShortcut);
  });

  return (
    <>
      <div ref={composerRef} className="mx-auto w-full max-w-3xl">
        <InputGroup className="chat-glass-input min-h-16 rounded-3xl border-border p-2 shadow-md">
          {isVoiceInputActive ? (
            <div
              aria-label="Entrada de voz em andamento"
              className="flex min-h-12 min-w-0 flex-1 items-center gap-3 px-2"
              role="status"
            >
              <Microphone className="shrink-0" />
              <AudioVisualizer active={speechRecognition.isListening} />
              <span className="sr-only" aria-live="polite">
                {speechRecognition.transcript || "Pode falar"}
              </span>
            </div>
          ) : (
            <InputGroupTextarea
              aria-label="Digite sua mensagem"
              className="max-h-40 min-h-12"
              placeholder="Qual a sua duvida?"
              rows={1}
              value={draft}
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleSend();
                }
              }}
            />
          )}

          {isVoiceInputActive ? (
            <InputGroupAddon align="inline-end" className="mr-0! gap-2 p-0!">
              <Button
                aria-label="Cancelar entrada por voz"
                size="icon-lg"
                variant="outline"
                onClick={handleCancelVoiceInput}
              >
                <Xmark />
              </Button>
              <Tooltip>
                <TooltipTrigger
                  render={
                    <Button
                      aria-label="Enviar áudio"
                      disabled={!speechRecognition.transcript.trim()}
                      size="icon-lg"
                      variant="default"
                      onClick={handleSubmitVoiceInput}
                    >
                      <PaperPlane />
                    </Button>
                  }
                />
                <TooltipContent>Enviar áudio</TooltipContent>
              </Tooltip>
            </InputGroupAddon>
          ) : !hasDraft || !isStreaming ? (
            <InputGroupAddon
              align="inline-end"
              className="mr-0! gap-2 p-0!"
            >
              {!hasDraft ? (
              <Tooltip>
                <TooltipTrigger
                  render={
                    <Button
                      aria-label="Iniciar entrada por voz"
                      disabled={!speechRecognition.isSupported || isStreaming}
                      size="icon-lg"
                      variant="outline"
                      onClick={handleStartVoiceInput}
                    >
                      <Microphone />
                    </Button>
                  }
                />
                <TooltipContent>Ctrl + M</TooltipContent>
              </Tooltip>
              ) : null}

            {hasDraft && !isStreaming ? (
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    aria-label="Enviar mensagem"
                    size="icon-lg"
                    variant="default"
                    onClick={handleSend}
                  >
                    <PaperPlane />
                  </Button>
                }
              />
              <TooltipContent>Enviar mensagem</TooltipContent>
            </Tooltip>
            ) : null}
            </InputGroupAddon>
          ) : null}
        </InputGroup>
      </div>
    </>
  );
}
