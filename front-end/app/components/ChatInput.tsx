"use client";

import {useRef} from "react";
import {Button, TextArea} from "@heroui/react";
import {Microphone, PaperPlane} from "@gravity-ui/icons";

type ChatInputProps = {
  canSend: boolean;
  draft: string;
  isStreaming?: boolean;
  onDraftChange: (value: string) => void;
  onSend: () => void;
};

export function ChatInput({
  canSend,
  draft,
  isStreaming = false,
  onDraftChange,
  onSend,
}: ChatInputProps) {
  const composerRef = useRef<HTMLDivElement>(null);

  function focusInput() {
    requestAnimationFrame(() => {
      composerRef.current?.querySelector("textarea")?.focus();
    });
  }

  function handleSend() {
    if (!canSend || isStreaming) {
      return;
    }

    onSend();
    focusInput();
  }

  return (
    <div className="mx-auto w-full max-w-3xl">
      <div ref={composerRef} className="chat-composer rounded-3xl border bg-field px-3 py-2">
        <div className="flex min-h-12 items-center gap-2">
          <TextArea
            aria-label="Digite sua mensagem"
            className="chat-composer-textarea flex-1"
            placeholder="Pergunte alguma coisa"
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
              aria-label="Microfone"
              size="md"
              variant="outline"
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
  );
}
