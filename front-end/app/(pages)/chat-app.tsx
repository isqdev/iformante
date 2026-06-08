"use client";

import {startTransition, useEffect, useMemo, useState} from "react";
import {Toast, useOverlayState} from "@heroui/react";
import {useRouter} from "next/navigation";

import {ChatInput} from "../components/ChatInput";
import {ChatHeader} from "../components/ChatHeader";
import {ChatMessages} from "../components/ChatMessages";
import {DocumentModal} from "../components/DocumentModal";
import {SettingsModal} from "../components/SettingsModal";
import {Sidebar} from "../components/Sidebar";
import type {Conversation} from "../models/conversation";
import type {Message} from "../models/message";
import type {User} from "../models/user";

type ChatAppProps = {
  conversationId?: string;
};

type ConversationSummary = {
  id: string;
  title: string;
};

type ConversationPayload = ConversationSummary & {
  messages: Message[];
};

type SseEvent = {
  data: string;
  event: string;
};

const currentUser: User = {
  name: "Isaque Dias",
  role: "Discente",
};

export function ChatApp({conversationId}: ChatAppProps) {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] =
    useState<Conversation | null>(null);
  const [draft, setDraft] = useState("");

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const [isStreamingResponse, setIsStreamingResponse] = useState(false);

  const settingsModal = useOverlayState();
  const documentModal = useOverlayState();

  const canSend = draft.trim().length > 0;
  const isNewConversationActive = !activeConversation?.id;

  useEffect(() => {
    void loadConversations();
  }, []);

  useEffect(() => {
    if (!conversationId) {
      queueMicrotask(() => setActiveConversation(null));
      return;
    }

    void loadConversation(conversationId);
  }, [conversationId]);

  const chatMessages = useMemo(
    () => activeConversation?.messages ?? [],
    [activeConversation],
  );

  async function loadConversations() {
    const response = await fetch("/api/conversations", {cache: "no-store"});

    if (!response.ok) {
      setConversations([]);
      return;
    }

    const payload = (await response.json()) as ConversationSummary[];
    setConversations(
      payload.map((conversation) => ({
        ...conversation,
        messages: [],
      })),
    );
  }

  async function loadConversation(nextConversationId: string) {
    const response = await fetch(`/api/conversations/${nextConversationId}`, {
      cache: "no-store",
    });

    if (!response.ok) {
      setActiveConversation(null);
      return;
    }

    const payload = (await response.json()) as ConversationPayload;
    setActiveConversation(payload);
    setConversations((current) => upsertConversation(current, payload));
  }

  function handleNewConversation() {
    setActiveConversation(null);
    setDraft("");
    setIsMobileSidebarOpen(false);
    router.push("/");
  }

  function handleSelectConversation(nextConversationId: string) {
    setIsMobileSidebarOpen(false);
    router.push(`/c/${nextConversationId}`);
  }

  function updateAssistantMessage(
    conversationIdToUpdate: string | null,
    messageId: string,
    content: string,
    isStreaming: boolean,
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
                }
              : message,
          ),
        };
      });
    });
  }

  async function handleSendMessage() {
    const trimmedDraft = draft.trim();

    if (!trimmedDraft || isStreamingResponse) {
      return;
    }

    const existingConversationId = activeConversation?.id ?? null;
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmedDraft,
    };
    const assistantMessage: Message = {
      id: `assistant-${Date.now() + 1}`,
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
      void loadConversations();
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

        setConversations((items) => upsertConversation(items, nextConversation));
        return nextConversation;
      });

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

      throw new Error(payload.message ?? "Erro ao gerar resposta.");
    }

    return null;
  }

  return (
    <>
      <div className="flex h-screen overflow-hidden bg-white text-foreground">
        <Sidebar
          activeConversationId={activeConversation?.id ?? ""}
          conversations={conversations}
          currentUser={currentUser}
          isCollapsed={isSidebarCollapsed}
          isMobileOpen={isMobileSidebarOpen}
          isNewConversationActive={isNewConversationActive}
          onCloseMobile={() => setIsMobileSidebarOpen(false)}
          onNewDocument={documentModal.open}
          onNewConversation={handleNewConversation}
          onOpenSettings={settingsModal.open}
          onSelectConversation={handleSelectConversation}
          onToggleCollapse={() => setIsSidebarCollapsed((current) => !current)}
        />

        <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-white">
          <ChatHeader
            title={activeConversation?.title ?? "Nova conversa"}
            onOpenMobileSidebar={() => setIsMobileSidebarOpen(true)}
          />

          <section className="flex min-h-0 flex-1 flex-col">
            {chatMessages.length > 0 ? (
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
                      Qual a sua duvida sobre o IF?
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

        <DocumentModal state={documentModal} />
        <SettingsModal state={settingsModal} user={currentUser} />
      </div>
      <Toast.Provider placement="top end" />
    </>
  );
}

function upsertConversation(
  conversations: Conversation[],
  conversation: Conversation,
) {
  const existingConversation = conversations.find(
    (item) => item.id === conversation.id,
  );

  if (!existingConversation) {
    return [conversation, ...conversations];
  }

  return conversations.map((item) =>
    item.id === conversation.id
      ? {
          ...item,
          ...conversation,
          messages:
            conversation.messages.length > 0
              ? conversation.messages
              : item.messages,
        }
      : item,
  );
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
