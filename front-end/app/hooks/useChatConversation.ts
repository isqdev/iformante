"use client";
import { startTransition, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuth } from "../components/auth/AuthProvider";
import { useSidebar } from "../components/sidebar/SidebarProvider";
import type { Conversation } from "../models/conversation";
import type { Message, MessageSource } from "../models/message";
import { readChatStream, type SseEvent } from "@/lib/chat-stream";
type ConversationPayload = { id: string; title: string; messages: Message[] };
export function useChatConversation(conversationId?: string) {
  const { user, loading: authLoading } = useAuth();
  const userId = user?.id;
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

  const pendingRequest = useRef<AbortController | null>(null);
  useEffect(() => () => pendingRequest.current?.abort(), []);

  const canSend = !authLoading && draft.trim().length > 0;
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
    if (authLoading) return;
    if (conversationId && !userId) {
      router.replace("/");
      return;
    }
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
  }, [conversationId, router, authLoading, userId]);

  useEffect(() => {
    pendingRequest.current?.abort();
    queueMicrotask(() => {
      setIsStreamingResponse(false);
      setActiveConversation(null);
      setDraft("");
      setIsLoadingConversation(false);
      setSelectedSource(null);
    });
  }, [newConversationVersion, user?.id]);

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

    if (authLoading || !trimmedDraft || isStreamingResponse) {
      return;
    }

    const existingConversationId = activeConversation?.id ?? null;
    const optimisticConversationId =
      !user || existingConversationId
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

    const controller = new AbortController();
    pendingRequest.current = controller;
    let resolvedConversationId = existingConversationId;
    let assistantContent = "";

    try {
      const response = await fetch("/api/chat", {
        signal: controller.signal,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          conversation_id: existingConversationId,
          message: trimmedDraft,
          messages: [
            ...(activeConversation?.messages ?? [])
              .filter((m) => !m.isStreaming)
              .map(({ role, content }) => ({ role, content })),
            { role: "user", content: trimmedDraft },
          ],
        }),
      });

      if (!response.ok || !response.body) {
        const errorPayload = (await response.json().catch(() => null)) as {
          error?: string;
        } | null;

        throw new Error(
          errorPayload?.error ?? "Nao foi possivel iniciar a resposta da IA.",
        );
      }

      for await (const event of readChatStream(response)) {
        const nextConversationId = handleSseEvent({
          assistantMessageId: assistantMessage.id,
          currentAssistantContent: assistantContent,
          event,
          fallbackTitle: trimmedDraft,
          optimisticConversationId,
          resolvedConversationId,
        });
        if (event.event === "delta")
          assistantContent +=
            (JSON.parse(event.data) as { content?: string }).content ?? "";
        if (nextConversationId) resolvedConversationId = nextConversationId;
      }

      updateAssistantMessage(
        resolvedConversationId,
        assistantMessage.id,
        assistantContent,
        false,
      );
      void refreshConversations();
    } catch (error) {
      if (controller.signal.aborted) return;
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
      if (pendingRequest.current === controller) {
        pendingRequest.current = null;
        setIsStreamingResponse(false);
      }
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
      const payload = JSON.parse(event.data) as { content?: string };
      const nextContent = currentAssistantContent + (payload.content ?? "");

      updateAssistantMessage(
        resolvedConversationId,
        assistantMessageId,
        nextContent,
        true,
      );
    }

    if (event.event === "rag") {
      const payload = JSON.parse(event.data) as { active?: boolean };

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
      const payload = JSON.parse(event.data) as { message?: string };
      const errorMessage = payload.message ?? "Erro ao gerar resposta.";

      if (
        errorMessage
          .toLocaleLowerCase("pt-BR")
          .includes("conversa nao encontrada")
      ) {
        router.replace("/");
        toast.warning("Chat não encontrado");
      }

      throw new Error(errorMessage);
    }

    if (event.event === "done") {
      const payload = JSON.parse(event.data) as { sources?: MessageSource[] };

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

  return {
    activeConversation,
    chatMessages,
    draft,
    setDraft,
    isStreamingResponse,
    selectedSource,
    setSelectedSource,
    isDesktopLayout,
    shouldShowConversationSkeleton,
    canSend,
    newConversationVersion,
    handleSendMessage,
  };
}
function createTemporaryMessageId(role: "assistant" | "user") {
  return `${role}-${crypto.randomUUID()}`;
}
