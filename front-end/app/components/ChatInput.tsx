"use client";

import {useEffect, useRef} from "react";
import {Button, TextArea, Toast, useOverlayState} from "@heroui/react";
import {Microphone, PaperPlane} from "@gravity-ui/icons";

import {useSpeechRecognition} from "../hooks/useSpeechRecognition";
import {VoiceInputModal} from "./VoiceInputModal";

type ChatInputProps = {
  canSend: boolean;
  draft: string;
  isStreaming?: boolean;
  onDraftChange: (value: string) => void;
  onSend: (message?: string) => void;
};

export function ChatInput({
  canSend,
  draft,
  isStreaming = false,
  onDraftChange,
  onSend,
}: ChatInputProps) {
  const composerRef = useRef<HTMLDivElement>(null);
  const voiceModal = useOverlayState();
  const speechRecognition = useSpeechRecognition({
    onError: (message) => {
      voiceModal.close();
      Toast.toast.danger(message);
      focusInput();
    },
    onFinalTranscript: (transcript) => {
      voiceModal.close();
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

    voiceModal.open();

    if (!speechRecognition.start()) {
      voiceModal.close();
    }
  }

  function handleCancelVoiceInput() {
    speechRecognition.cancel();
    voiceModal.close();
    focusInput();
  }

  useEffect(() => {
    function handleVoiceShortcut(event: KeyboardEvent) {
      if (
        event.key.toLowerCase() !== "m" ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.repeat ||
        isEditableElement(document.activeElement) ||
        voiceModal.isOpen ||
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
      <div className="mx-auto w-full max-w-3xl">
        <div ref={composerRef} className="chat-composer rounded-3xl border bg-field px-3 py-2">
          <div className="flex min-h-12 items-center gap-2">
            <TextArea
              aria-label="Digite sua mensagem"
              className="chat-composer-textarea flex-1"
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

            {draft.trim().length === 0 ? (
              <Button
                isIconOnly
                aria-label="Iniciar entrada por voz"
                isDisabled={!speechRecognition.isSupported || isStreaming}
                size="md"
                variant="outline"
                onPress={handleStartVoiceInput}
              >
                <Microphone className="h-5 w-5" />
              </Button>
            ) : null}

            <Button
              isIconOnly
              aria-label="Enviar mensagem"
              isDisabled={!canSend || isStreaming}
              size="md"
              variant="primary"
              onPress={handleSend}
            >
              <PaperPlane className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </div>

      <VoiceInputModal
        isListening={speechRecognition.isListening}
        state={voiceModal}
        transcript={speechRecognition.transcript}
        onCancel={handleCancelVoiceInput}
      />
    </>
  );
}

function isEditableElement(element: Element | null) {
  if (!(element instanceof HTMLElement)) {
    return false;
  }

  return Boolean(
    element.closest(
      'input, textarea, select, [contenteditable="true"], [role="textbox"]',
    ),
  );
}
