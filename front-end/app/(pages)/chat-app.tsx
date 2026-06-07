"use client";

import {startTransition, useState} from "react";
import {Toast, useOverlayState} from "@heroui/react";

import {ChatInput} from "../components/ChatInput";
import {ChatHeader} from "../components/ChatHeader";
import {ChatMessages} from "../components/ChatMessages";
import {DocumentModal} from "../components/DocumentModal";
import {SettingsModal} from "../components/SettingsModal";
import {Sidebar} from "../components/Sidebar";
import type {Conversation} from "../models/conversation";
import type {Message} from "../models/message";
import type {User} from "../models/user";

const initialConversations: Conversation[] = [
  {
    id: "conv-1",
    title: "Calendario academico 2026",
    messages: [],
  },
  {
    id: "conv-2",
    title: "Bolsas e auxilios estudantis",
    messages: [],
  },
  {
    id: "conv-3",
    title: "Atendimento da biblioteca",
    messages: [],
  },
];

const currentUser: User = {
  name: "Isaque Dias",
  role: "Discente",
};

export function ChatApp() {
  const [conversations, setConversations] = useState<Conversation[]>(initialConversations);
  const [activeConversationId, setActiveConversationId] = useState(initialConversations[0]?.id ?? "");
  const [draft, setDraft] = useState("");

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);

  const [isStreamingResponse, setIsStreamingResponse] = useState(false);

  const settingsModal = useOverlayState();
  const documentModal = useOverlayState();

  const activeConversation =
    conversations.find((conversation) => conversation.id === activeConversationId) ??
    conversations[0] ??
    null;

  const canSend = draft.trim().length > 0;

  function handleNewConversation() {
    const nextConversation: Conversation = {
      id: `conv-${Date.now()}`,
      title: `Nova conversa ${conversations.length + 1}`,
      messages: [],
    };

    setConversations((current) => [nextConversation, ...current]);
    setActiveConversationId(nextConversation.id);
    setDraft("");
    setIsMobileSidebarOpen(false);
  }

  function handleSelectConversation(conversationId: string) {
    setActiveConversationId(conversationId);
    setIsMobileSidebarOpen(false);
  }

  function updateAssistantMessage(
    conversationId: string,
    messageId: string,
    content: string,
    isStreaming: boolean,
  ) {
    startTransition(() => {
      setConversations((current) =>
        current.map((conversation) =>
          conversation.id === conversationId
            ? {
                ...conversation,
                messages: conversation.messages.map((message) =>
                  message.id === messageId
                    ? {
                        ...message,
                        content,
                        isStreaming,
                      }
                    : message,
                ),
              }
            : conversation,
        ),
      );
    });
  }

  async function handleSendMessage() {
    const trimmedDraft = draft.trim();

    if (!trimmedDraft || !activeConversation || isStreamingResponse) {
      return;
    }

    const conversationId = activeConversation.id;
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

    const nextMessages = [...activeConversation.messages, userMessage, assistantMessage];
    const messagesForModel = [...activeConversation.messages, userMessage]
      .filter((message) => message.content.trim().length > 0)
      .map((message) => ({
        role: message.role,
        content: message.content.trim(),
      }));

    setConversations((current) =>
      current.map((conversation) =>
        conversation.id === conversationId
          ? {
              ...conversation,
              title:
                conversation.messages.length === 0
                  ? trimmedDraft.slice(0, 48)
                  : conversation.title,
              messages: nextMessages,
            }
          : conversation,
      ),
    );

    setDraft("");
    setIsStreamingResponse(true);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messages: messagesForModel,
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
      let assistantContent = "";

      while (true) {
        const {done, value} = await reader.read();

        if (done) {
          break;
        }

        assistantContent += decoder.decode(value, {stream: true});
        updateAssistantMessage(
          conversationId,
          assistantMessage.id,
          assistantContent,
          true,
        );
      }

      assistantContent += decoder.decode();
      updateAssistantMessage(
        conversationId,
        assistantMessage.id,
        assistantContent,
        false,
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Nao foi possivel obter resposta da IA.";

      updateAssistantMessage(conversationId, assistantMessage.id, message, false);
    } finally {
      setIsStreamingResponse(false);
    }
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
            {activeConversation && activeConversation.messages.length > 0 ? (
              <>
                <ChatMessages messages={activeConversation.messages} />

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
                      Qual a sua dúvida sobre o IF?
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
