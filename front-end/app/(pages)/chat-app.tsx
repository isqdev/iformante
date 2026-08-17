"use client";

import {startTransition, useEffect, useMemo, useState} from "react";
import {useRouter} from "next/navigation";
import {toast} from "sonner";
import {cn} from "@/lib/utils";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import {Card} from "@/components/ui/card";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetTitle,
} from "@/components/ui/sheet";

import {ChatInput} from "../components/ChatInput";
import {ChatHeader} from "../components/ChatHeader";
import {ChatMessages} from "../components/ChatMessages";
import {PdfViewer} from "../components/PdfViewer";
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
    addOptimisticConversation,
    refreshConversations,
    removeOptimisticConversation,
    replaceOptimisticConversation,
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
  const [selectedSource, setSelectedSource] = useState<MessageSource | null>(
    null,
  );
  const [isDesktopLayout, setIsDesktopLayout] = useState(false);

  const canSend = draft.trim().length > 0;
  const shouldShowConversationSkeleton =
    Boolean(conversationId) &&
    (isLoadingConversation || activeConversation?.id !== conversationId);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(min-width: 1024px)");
    const updateLayout = () => setIsDesktopLayout(mediaQuery.matches);

    updateLayout();
    mediaQuery.addEventListener("change", updateLayout);
    return () => mediaQuery.removeEventListener("change", updateLayout);
  }, []);

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
          toast.warning("Chat não encontrado");
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
          toast.warning("Chat não encontrado");
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
      setSelectedSource(null);
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
    usesRag?: boolean,
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
                  usesRag: usesRag ?? message.usesRag,
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
    const optimisticConversationId = existingConversationId
      ? null
      : `optimistic-${crypto.randomUUID()}`;
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
    if (optimisticConversationId) {
      addOptimisticConversation({
        id: optimisticConversationId,
        title: localConversation.title,
      });
    }
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
            optimisticConversationId,
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
          optimisticConversationId,
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
      if (optimisticConversationId && !resolvedConversationId) {
        removeOptimisticConversation(optimisticConversationId);
      }

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
    optimisticConversationId,
    resolvedConversationId,
  }: {
    assistantMessageId: string;
    currentAssistantContent: string;
    event: SseEvent;
    fallbackTitle: string;
    optimisticConversationId: string | null;
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
      if (optimisticConversationId) {
        replaceOptimisticConversation(optimisticConversationId, {
          id: payload.conversation_id,
          title: payload.title || fallbackTitle.slice(0, 48),
        });
      }

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

    if (event.event === "rag") {
      const payload = JSON.parse(event.data) as {active?: boolean};

      updateAssistantMessage(
        resolvedConversationId,
        assistantMessageId,
        currentAssistantContent,
        true,
        undefined,
        payload.active === true,
      );
    }

    if (event.event === "error") {
      const payload = JSON.parse(event.data) as {message?: string};
      const errorMessage = payload.message ?? "Erro ao gerar resposta.";

      if (errorMessage.toLocaleLowerCase("pt-BR").includes("conversa nao encontrada")) {
        router.replace("/");
        toast.warning("Chat não encontrado");
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

  const chatContent = (
    <Card
      className={cn(
        "mt-2 mr-2 mb-2 ml-2 h-[calc(100%-1rem)] min-w-0 gap-0 rounded-lg border border-sidebar-border bg-sidebar py-0 shadow-sm ring-0 md:ml-0",
        isDesktopLayout && selectedSource && "md:mr-1",
      )}
    >
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-transparent!">
        <ChatHeader
          isLoading={shouldShowConversationSkeleton}
          title={activeConversation?.title ?? ""}
        />

        <section className="relative flex min-h-0 flex-1 flex-col">
          {shouldShowConversationSkeleton ? (
            <ChatSkeleton />
          ) : chatMessages.length > 0 ? (
            <>
              <ChatMessages
                messages={chatMessages}
                onOpenSource={setSelectedSource}
              />

              <div className="pointer-events-none absolute inset-x-0 bottom-0 px-4 py-4 md:px-6">
                <div className="pointer-events-auto">
                  <ChatInput
                    canSend={canSend}
                    draft={draft}
                    focusKey={`${conversationId ?? "new"}:${newConversationVersion}`}
                    isStreaming={isStreamingResponse}
                    onDraftChange={setDraft}
                    onSend={handleSendMessage}
                  />
                </div>
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
                  focusKey={`${conversationId ?? "new"}:${newConversationVersion}`}
                  isStreaming={isStreamingResponse}
                  onDraftChange={setDraft}
                  onSend={handleSendMessage}
                />
              </div>
            </div>
          )}
        </section>
      </main>
    </Card>
  );

  if (isDesktopLayout && selectedSource) {
    return (
      <ResizablePanelGroup orientation="horizontal">
        <ResizablePanel defaultSize="58%" minSize="40%">
          {chatContent}
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize="42%" minSize="30%">
          <Card className="mt-2 mr-2 mb-2 ml-1 h-[calc(100%-1rem)] gap-0 rounded-lg border border-sidebar-border bg-sidebar py-0 shadow-sm ring-0">
            <PdfViewer
              key={selectedSource.document_id}
              filename={selectedSource.filename}
              url={`/api/documents/${encodeURIComponent(selectedSource.document_id)}/content`}
              onClose={() => setSelectedSource(null)}
            />
          </Card>
        </ResizablePanel>
      </ResizablePanelGroup>
    );
  }

  return (
    <>
      {chatContent}
      <Sheet
        open={Boolean(selectedSource)}
        onOpenChange={(open) => {
          if (!open) setSelectedSource(null);
        }}
      >
        <SheetContent
          className="w-full gap-0 p-0 sm:max-w-none"
          showCloseButton={false}
        >
          <SheetTitle className="sr-only">
            {selectedSource?.filename ?? "Visualizador de PDF"}
          </SheetTitle>
          <SheetDescription className="sr-only">
            Visualizacao do documento armazenado.
          </SheetDescription>
          {selectedSource ? (
            <PdfViewer
              key={selectedSource.document_id}
              filename={selectedSource.filename}
              url={`/api/documents/${encodeURIComponent(selectedSource.document_id)}/content`}
              onClose={() => setSelectedSource(null)}
            />
          ) : null}
        </SheetContent>
      </Sheet>
    </>
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
