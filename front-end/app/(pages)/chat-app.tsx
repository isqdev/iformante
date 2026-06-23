"use client";

import {startTransition, useEffect, useMemo, useState} from "react";
import {useRouter} from "next/navigation";
import {Toast} from "@heroui/react";

import {ChatInput} from "../components/ChatInput";
import {ChatHeader} from "../components/ChatHeader";
import {ChatMessages} from "../components/ChatMessages";
import {ChatSkeleton} from "../components/Skelentons";
import {useSidebar} from "../components/sidebar/SidebarProvider";
import type {Conversation} from "../models/conversation";
import type {Message, MessageSource} from "../models/message";

type ChatAppProps = {
  conversationId?: string;
};

type ConversationPayload = {
  id: string;
  title: string;
  messages: Message[];
};

type SseEvent = {
  data: string;
  event: string;
};

export function ChatApp({conversationId}: ChatAppProps) {
  const router = useRouter();
  const {
    openMobileSidebar,
    refreshConversations,
    setActiveConversationId,
    newConversationVersion,
  } = useSidebar();
  const [activeConversation, setActiveConversation] =
    useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");
  const [isLoadingConversation, setIsLoadingConversation] = useState(
    Boolean(conversationId),
  );
  const [isStreamingResponse, setIsStreamingResponse] = useState(false);

  const canSend = draft.trim().length > 0;
  const shouldShowConversationSkeleton =
    Boolean(conversationId) &&
    (isLoadingConversation || activeConversation?.id !== conversationId);

  useEffect(() => {
    if (!conversationId) {
      queueMicrotask(() => {
        setActiveConversation(null);
        setIsLoadingConversation(false);
      });
      return;
    }

    let isCancelled = false;
    queueMicrotask(() => {
      if (!isCancelled) {
        setIsLoadingConversation(true);
      }
    });

    void (async () => {
      try {
        const response = await fetch(`/api/conversations/${conversationId}`, {
          cache: "no-store",
        });

        if (isCancelled) {
          return;
        }

        if (!response.ok) {
          setActiveConversation(null);
          router.replace("/");
          Toast.toast.warning("Chat não encontrado");
          return;
        }

        const payload = (await response.json()) as ConversationPayload;

        if (!isCancelled) {
          setActiveConversation(payload);
        }
      } catch {
        if (!isCancelled) {
          setActiveConversation(null);
          router.replace("/");
          Toast.toast.warning("Chat não encontrado");
        }
      } finally {
        if (!isCancelled) {
          setIsLoadingConversation(false);
        }
      }
    })();

    return () => {
      isCancelled = true;
    };
  }, [conversationId, router]);

  useEffect(() => {
    queueMicrotask(() => {
      setActiveConversation(null);
      setDraft("");
      setIsLoadingConversation(false);
    });
  }, [newConversationVersion]);

  const chatMessages = useMemo(
    () => activeConversation?.messages ?? [],
    [activeConversation],
  );

  function updateAssistantMessage(
    conversationIdToUpdate: string | null,
    messageId: string,
    content: string,
    isStreaming: boolean,
    sources?: MessageSource[],
  ) {
    startTransition(() => {
      setActiveConversation((current) => {
        if (
          !current ||
          (current.id !== conversationIdToUpdate && current.id !== "")
        ) {
          return current;
        }

        return {
          ...current,
          messages: current.messages.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  content,
                  isStreaming,
                  sources: sources ?? message.sources,
                }
              : message,
          ),
        };
      });
    });
  }

  async function handleSendMessage(message?: string) {
    const trimmedDraft = (message ?? draft).trim();

    if (!trimmedDraft || isStreamingResponse) {
      return;
    }

    const existingConversationId = activeConversation?.id ?? null;
    const userMessage: Message = {
      id: createTemporaryMessageId("user"),
      role: "user",
      content: trimmedDraft,
    };
    const assistantMessage: Message = {
      id: createTemporaryMessageId("assistant"),
      role: "assistant",
      content: "",
      isStreaming: true,
    };
    const localConversation: Conversation = activeConversation
      ? {
          ...activeConversation,
          messages: [
            ...activeConversation.messages,
            userMessage,
            assistantMessage,
          ],
        }
      : {
          id: "",
          title: trimmedDraft.slice(0, 48),
          messages: [userMessage, assistantMessage],
        };

    setActiveConversation(localConversation);
    setDraft("");
    setIsStreamingResponse(true);

    let resolvedConversationId = existingConversationId;
    let assistantContent = "";

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conversation_id: existingConversationId,
          message: trimmedDraft,
        }),
      });

      if (!response.ok || !response.body) {
        const errorPayload = (await response.json().catch(() => null)) as
          | {error?: string}
          | null;

        throw new Error(
          errorPayload?.error ?? "Nao foi possivel iniciar a resposta da IA.",
        );
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const {done, value} = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, {stream: true});
        const result = processSseBuffer(buffer, (event) => {
          const nextConversationId = handleSseEvent({
            assistantMessageId: assistantMessage.id,
            currentAssistantContent: assistantContent,
            event,
            fallbackTitle: trimmedDraft,
            resolvedConversationId,
          });

          if (event.event === "delta") {
            const payload = JSON.parse(event.data) as {content?: string};
            assistantContent += payload.content ?? "";
          }

          if (nextConversationId) {
            resolvedConversationId = nextConversationId;
          }
        });
        buffer = result;
      }

      buffer += decoder.decode();
      processSseBuffer(buffer, (event) => {
        const nextConversationId = handleSseEvent({
          assistantMessageId: assistantMessage.id,
          currentAssistantContent: assistantContent,
          event,
          fallbackTitle: trimmedDraft,
          resolvedConversationId,
        });

        if (event.event === "delta") {
          const payload = JSON.parse(event.data) as {content?: string};
          assistantContent += payload.content ?? "";
        }

        if (nextConversationId) {
          resolvedConversationId = nextConversationId;
        }
      });

      updateAssistantMessage(
        resolvedConversationId,
        assistantMessage.id,
        assistantContent,
        false,
      );
      void refreshConversations();
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Nao foi possivel obter resposta da IA.";

      updateAssistantMessage(
        resolvedConversationId,
        assistantMessage.id,
        message,
        false,
      );
    } finally {
      setIsStreamingResponse(false);
    }
  }

  function handleSseEvent({
    assistantMessageId,
    currentAssistantContent,
    event,
    fallbackTitle,
    resolvedConversationId,
  }: {
    assistantMessageId: string;
    currentAssistantContent: string;
    event: SseEvent;
    fallbackTitle: string;
    resolvedConversationId: string | null;
  }): string | null {
    if (event.event === "conversation") {
      const payload = JSON.parse(event.data) as {
        conversation_id: string;
        title: string;
      };

      setActiveConversation((current) => {
        const nextConversation: Conversation = {
          id: payload.conversation_id,
          title: payload.title || fallbackTitle.slice(0, 48),
          messages: current?.messages ?? [],
        };

        return nextConversation;
      });
      setActiveConversationId(payload.conversation_id);

      if (!resolvedConversationId) {
        window.history.replaceState(null, "", `/c/${payload.conversation_id}`);
      }

      return payload.conversation_id;
    }

    if (event.event === "delta") {
      const payload = JSON.parse(event.data) as {content?: string};
      const nextContent = currentAssistantContent + (payload.content ?? "");

      updateAssistantMessage(
        resolvedConversationId,
        assistantMessageId,
        nextContent,
        true,
      );
    }

    if (event.event === "error") {
      const payload = JSON.parse(event.data) as {message?: string};
      const errorMessage = payload.message ?? "Erro ao gerar resposta.";

      if (errorMessage.toLocaleLowerCase("pt-BR").includes("conversa nao encontrada")) {
        router.replace("/");
        Toast.toast.warning("Chat não encontrado");
      }

      throw new Error(errorMessage);
    }

    if (event.event === "done") {
      const payload = JSON.parse(event.data) as {sources?: MessageSource[]};

      updateAssistantMessage(
        resolvedConversationId,
        assistantMessageId,
        currentAssistantContent,
        false,
        payload.sources ?? [],
      );
    }

    return null;
  }

  return (
    <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-white">
      <ChatHeader
        isLoading={shouldShowConversationSkeleton}
        title={activeConversation?.title ?? ""}
        onOpenMobileSidebar={openMobileSidebar}
      />

      <section className="flex min-h-0 flex-1 flex-col">
        {shouldShowConversationSkeleton ? (
          <ChatSkeleton />
        ) : chatMessages.length > 0 ? (
          <>
            <ChatMessages messages={chatMessages} />

            <div className="px-4 py-4 md:px-6">
              <ChatInput
                canSend={canSend}
                draft={draft}
                isStreaming={isStreamingResponse}
                onDraftChange={setDraft}
                onSend={handleSendMessage}
              />
            </div>
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center px-4 py-8 md:px-6">
            <div className="w-full max-w-3xl">
              <div className="mb-10 text-center">
                <h1 className="text-3xl font-semibold">
                  Pergunte sobre o IF!
                </h1>
              </div>

              <ChatInput
                canSend={canSend}
                draft={draft}
                isStreaming={isStreamingResponse}
                onDraftChange={setDraft}
                onSend={handleSendMessage}
              />
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

function createTemporaryMessageId(role: "assistant" | "user") {
  return `${role}-${crypto.randomUUID()}`;
}

function processSseBuffer(
  buffer: string,
  onEvent: (event: SseEvent) => void,
) {
  const blocks = buffer.split("\n\n");
  const nextBuffer = blocks.pop() ?? "";

  for (const block of blocks) {
    const event = parseSseEvent(block);

    if (event) {
      onEvent(event);
    }
  }

  return nextBuffer;
}

function parseSseEvent(block: string): SseEvent | null {
  const eventLine = block
    .split("\n")
    .find((line) => line.startsWith("event: "));
  const dataLine = block
    .split("\n")
    .find((line) => line.startsWith("data: "));

  if (!eventLine || !dataLine) {
    return null;
  }

  return {
    event: eventLine.slice("event: ".length),
    data: dataLine.slice("data: ".length),
  };
}
