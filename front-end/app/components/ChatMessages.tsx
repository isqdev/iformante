"use client";

import {type ClipboardEvent, useEffect, useRef, useState} from "react";
import {
  Copy,
  FaceRobot,
  FileText,
} from "@gravity-ui/icons";
import {Bouncy} from "ldrs/react";
import {toast} from "sonner";
import "ldrs/react/Bouncy.css";
import {
  Bubble,
  BubbleContent,
  BubbleReactions,
} from "@/components/ui/bubble";
import {Button} from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {Message, MessageContent} from "@/components/ui/message";
import {
  Marker,
  MarkerContent,
  MarkerIcon,
} from "@/components/ui/marker";
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller";

import type {
  Message as ChatMessage,
  MessageSource,
} from "../models/message";
import {ParseMarkdown} from "./ParseMarkdown";

type ChatMessagesProps = {
  messages: ChatMessage[];
  onOpenSource: (source: MessageSource) => void;
};

const STREAMING_STATUS_MESSAGES = [
  "Entendendo sua pergunta...",
  "Lendo as entrelinhas...",
  "Revirando os documentos...",
  "Garimpando informações...",
  "Vasculhando os arquivos...",
  "Dando uma passada na secretaria...",
  "Montando o quebra-cabeça...",
  "Cozinhando a resposta...",
  "Organizando as ideias...",
  "Quase lá...",
  "Só mais um segundo...",
  "Procurando a papelada...",
  "Juntando as peças que faltavam...",
  "Escrevendo isso a lápis primeiro...",
  "Folheando página por página...",
  "Abrindo as gavetas...",
  "Procurando debaixo da impressora...",
  "Checando se não caiu atrás da mesa...",
  "Olhando na coordenação...",
  "Bisbilhotando os anexos",
];
const SHIMMER_PASSES_DURATION_MS = 4000;
const STATUS_TRANSITION_DURATION_MS = 250;

function createShuffledMessageIndexes(excludedIndex: number) {
  const indexes = STREAMING_STATUS_MESSAGES.map((_, index) => index).filter(
    (index) => index !== excludedIndex,
  );

  for (let index = indexes.length - 1; index > 0; index -= 1) {
    const randomIndex = Math.floor(Math.random() * (index + 1));
    [indexes[index], indexes[randomIndex]] = [
      indexes[randomIndex],
      indexes[index],
    ];
  }

  return indexes;
}

function StreamingStatus({showMessage}: {showMessage: boolean}) {
  const [messageIndex, setMessageIndex] = useState<number | null>(null);
  const [isVisible, setIsVisible] = useState(true);
  const remainingMessageIndexes = useRef<number[]>([]);

  useEffect(() => {
    if (!showMessage) {
      return;
    }

    const initialIndex = Math.floor(
      Math.random() * STREAMING_STATUS_MESSAGES.length,
    );
    setMessageIndex(initialIndex);
    remainingMessageIndexes.current = createShuffledMessageIndexes(initialIndex);

    let displayTimeout: ReturnType<typeof setTimeout> | undefined;
    let transitionTimeout: ReturnType<typeof setTimeout> | undefined;

    function scheduleNextMessage() {
      displayTimeout = setTimeout(() => {
        setIsVisible(false);
      transitionTimeout = setTimeout(() => {
        setMessageIndex((currentIndex) => {
          const activeIndex = currentIndex ?? initialIndex;

          if (remainingMessageIndexes.current.length === 0) {
            remainingMessageIndexes.current =
              createShuffledMessageIndexes(activeIndex);
          }

          return remainingMessageIndexes.current.shift() ?? activeIndex;
        });
        setIsVisible(true);
        scheduleNextMessage();
      }, STATUS_TRANSITION_DURATION_MS);
      }, SHIMMER_PASSES_DURATION_MS);
    }

    scheduleNextMessage();

    return () => {
      if (displayTimeout) clearTimeout(displayTimeout);
      if (transitionTimeout) clearTimeout(transitionTimeout);
    };
  }, [showMessage]);

  return (
    <Marker
      aria-live="polite"
      className="flex min-h-6 items-center gap-2.5"
      role="status"
    >
      <Bouncy
        aria-label="Gerando resposta"
        color="var(--primary)"
        size="24"
        speed="1.75"
      />
      {showMessage ? (
        <MarkerContent
          className={
            "shimmer text-sm text-muted-foreground transition-all duration-300 ease-out motion-reduce:transition-none " +
            (isVisible
              ? "translate-y-0 opacity-100"
              : "translate-y-1 opacity-0")
          }
        >
          {messageIndex === null
            ? null
            : STREAMING_STATUS_MESSAGES[messageIndex]}
        </MarkerContent>
      ) : null}
    </Marker>
  );
}

export function ChatMessages({messages, onOpenSource}: ChatMessagesProps) {
  return (
    <MessageScrollerProvider autoScroll>
      <MessageScroller>
        <MessageScrollerViewport>
          <MessageScrollerContent className="mx-auto w-full max-w-3xl px-4 pt-8 pb-28 md:px-6">
            {messages.map((message) => {
              const isUser = message.role === "user";

              return (
                <MessageScrollerItem
                  key={message.id}
                  messageId={message.id}
                  scrollAnchor={isUser}
                >
                  <Message align={isUser ? "end" : "start"}>
                    <MessageContent>
                      {isUser ? (
                        <Bubble align="end">
                          <BubbleContent onCopy={handleUserMessageSelectionCopy}>
                            <ParseMarkdown content={message.content} />
                          </BubbleContent>
                          <BubbleReactions
                            align="end"
                            className="bg-transparent p-0 opacity-0 ring-0 transition-opacity group-hover/bubble:opacity-100 focus-within:opacity-100"
                            side="bottom"
                          >
                            <Button
                              aria-label="Copiar mensagem"
                              size="icon-xs"
                              variant="ghost"
                              onClick={copyUserMessage}
                            >
                              <Copy />
                            </Button>
                          </BubbleReactions>
                        </Bubble>
                      ) : (
                        <article className="w-full max-w-none text-base leading-7">
                          {message.content ? (
                            <ParseMarkdown content={message.content} />
                          ) : null}
                          {message.isStreaming && !message.content ? (
                            <StreamingStatus
                              showMessage={message.usesRag === true}
                            />
                          ) : null}
                          {!message.isStreaming && message.sources?.length ? (
                            <>
                            <Marker
                              aria-label="InFormante"
                              className="mt-4 before:bg-source-card-border after:bg-source-card-border"
                              variant="separator"
                            >
                              <MarkerIcon className="text-source-card-border">
                                <FaceRobot />
                              </MarkerIcon>
                            </Marker>
                            <Card className="mt-6 w-full border border-source-card-border bg-transparent font-serif ring-0">
                              <CardHeader>
                                <CardTitle className="font-serif text-lg font-semibold leading-normal tracking-wide">
                                  Fontes
                                </CardTitle>
                              </CardHeader>
                              <CardContent className="flex flex-col gap-2">
                                {message.sources.map((source) => (
                                  <div
                                    key={source.document_id}
                                    className="flex min-w-0 gap-2"
                                  >
                                    <Button
                                      className="min-w-0 flex-1 justify-start"
                                      variant="source"
                                      onClick={() => onOpenSource(source)}
                                    >
                                      <FileText data-icon="inline-start" />
                                      <span className="min-w-0 truncate">
                                        {source.filename}
                                      </span>
                                    </Button>
                                  </div>
                                ))}
                              </CardContent>
                            </Card>
                            </>
                          ) : null}
                        </article>
                      )}
                    </MessageContent>
                  </Message>
                </MessageScrollerItem>
              );
            })}
          </MessageScrollerContent>
        </MessageScrollerViewport>
        <MessageScrollerButton className="bottom-24" />
      </MessageScroller>
    </MessageScrollerProvider>
  );
}

function handleUserMessageSelectionCopy(
  event: ClipboardEvent<HTMLDivElement>,
) {
  const selection = window.getSelection()?.toString() ?? "";

  if (!selection) {
    return;
  }

  event.preventDefault();
  event.clipboardData.setData("text/plain", normalizeCopiedText(selection));
}

async function copyUserMessage(
  event: React.MouseEvent<HTMLButtonElement>,
) {
  const bubble = event.currentTarget.closest("[data-slot=bubble]");
  const content = bubble?.querySelector("[data-slot=bubble-content]");
  const text = normalizeCopiedText(content?.textContent ?? "");

  if (!text) {
    return;
  }

  await navigator.clipboard.writeText(text);
  toast.success("Mensagem copiada");
}

function normalizeCopiedText(text: string) {
  return text.replace(/\s+/g, " ").trim();
}
