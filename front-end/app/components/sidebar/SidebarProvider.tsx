"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {usePathname, useRouter} from "next/navigation";

import type {Conversation} from "../../models/conversation";

type ConversationSummary = {
  id: string;
  title: string;
};

type SidebarContextValue = {
  activeConversationId: string;
  addOptimisticConversation: (conversation: ConversationSummary) => void;
  conversations: Conversation[];
  isLoadingConversations: boolean;
  isNewConversationActive: boolean;
  newConversationVersion: number;
  openDocuments: () => void;
  refreshConversations: () => Promise<void>;
  removeOptimisticConversation: (conversationId: string) => void;
  replaceOptimisticConversation: (
    optimisticId: string,
    conversation: ConversationSummary,
  ) => void;
  selectConversation: (conversationId: string) => void;
  setActiveConversationId: (conversationId: string) => void;
  startNewConversation: () => void;
};

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({children}: {children: ReactNode}) {
  const pathname = usePathname();
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState(
    getConversationId(pathname),
  );
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [newConversationVersion, setNewConversationVersion] = useState(0);

  const refreshConversations = useCallback(async (showLoading = false) => {
    if (showLoading) {
      setIsLoadingConversations(true);
    }

    try {
      const response = await fetch("/api/conversations", {cache: "no-store"});

      if (!response.ok) {
        if (showLoading) {
          setConversations([]);
        }
        return;
      }

      const payload = (await response.json()) as ConversationSummary[];
      setConversations(
        payload.map((conversation) => ({
          ...conversation,
          messages: [],
        })),
      );
    } catch {
      if (showLoading) {
        setConversations([]);
      }
    } finally {
      if (showLoading) {
        setIsLoadingConversations(false);
      }
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void refreshConversations(true));
  }, [refreshConversations]);

  useEffect(() => {
    queueMicrotask(() => {
      setActiveConversationId(getConversationId(pathname));
    });
  }, [pathname]);

  const value = useMemo<SidebarContextValue>(
    () => ({
      activeConversationId,
      addOptimisticConversation: (conversation) => {
        setConversations((current) => [
          {
            ...conversation,
            messages: [],
          },
          ...current.filter((item) => item.id !== conversation.id),
        ]);
      },
      conversations,
      isLoadingConversations,
      isNewConversationActive:
        pathname === "/" && activeConversationId.length === 0,
      newConversationVersion,
      openDocuments: () => {
        router.push("/docs");
      },
      refreshConversations,
      removeOptimisticConversation: (conversationId) => {
        setConversations((current) =>
          current.filter((conversation) => conversation.id !== conversationId),
        );
      },
      replaceOptimisticConversation: (optimisticId, conversation) => {
        setConversations((current) => [
          {
            ...conversation,
            messages: [],
          },
          ...current.filter(
            (item) =>
              item.id !== optimisticId && item.id !== conversation.id,
          ),
        ]);
      },
      selectConversation: (conversationId: string) => {
        if (conversationId.startsWith("optimistic-")) {
          return;
        }

        setActiveConversationId(conversationId);
        router.push(`/c/${conversationId}`);
      },
      setActiveConversationId,
      startNewConversation: () => {
        setActiveConversationId("");
        setNewConversationVersion((current) => current + 1);
        router.push("/");
      },
    }),
    [
      activeConversationId,
      conversations,
      isLoadingConversations,
      newConversationVersion,
      pathname,
      refreshConversations,
      router,
    ],
  );

  return (
    <SidebarContext.Provider value={value}>
      {children}
    </SidebarContext.Provider>
  );
}

export function useSidebar() {
  const context = useContext(SidebarContext);

  if (!context) {
    throw new Error("useSidebar deve ser usado dentro de SidebarProvider.");
  }

  return context;
}

function getConversationId(pathname: string) {
  const match = pathname.match(/^\/c\/([^/]+)$/);
  return match?.[1] ?? "";
}
