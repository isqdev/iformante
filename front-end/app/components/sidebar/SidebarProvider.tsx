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
  closeMobileSidebar: () => void;
  conversations: Conversation[];
  isCollapsed: boolean;
  isLoadingConversations: boolean;
  isMobileOpen: boolean;
  isNewConversationActive: boolean;
  newConversationVersion: number;
  openMobileSidebar: () => void;
  openDocuments: () => void;
  refreshConversations: () => Promise<void>;
  selectConversation: (conversationId: string) => void;
  setActiveConversationId: (conversationId: string) => void;
  startNewConversation: () => void;
  toggleCollapse: () => void;
};

const SidebarContext = createContext<SidebarContextValue | null>(null);

export function SidebarProvider({children}: {children: ReactNode}) {
  const pathname = usePathname();
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState(
    getConversationId(pathname),
  );
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [newConversationVersion, setNewConversationVersion] = useState(0);

  const refreshConversations = useCallback(async () => {
    setIsLoadingConversations(true);

    try {
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
    } catch {
      setConversations([]);
    } finally {
      setIsLoadingConversations(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void refreshConversations());
  }, [refreshConversations]);

  useEffect(() => {
    queueMicrotask(() => {
      setActiveConversationId(getConversationId(pathname));
      setIsMobileOpen(false);
    });
  }, [pathname]);

  const value = useMemo<SidebarContextValue>(
    () => ({
      activeConversationId,
      closeMobileSidebar: () => setIsMobileOpen(false),
      conversations,
      isCollapsed,
      isLoadingConversations,
      isMobileOpen,
      isNewConversationActive:
        pathname === "/" && activeConversationId.length === 0,
      newConversationVersion,
      openMobileSidebar: () => setIsMobileOpen(true),
      openDocuments: () => {
        setIsMobileOpen(false);
        router.push("/docs");
      },
      refreshConversations,
      selectConversation: (conversationId: string) => {
        setActiveConversationId(conversationId);
        setIsMobileOpen(false);
        router.push(`/c/${conversationId}`);
      },
      setActiveConversationId,
      startNewConversation: () => {
        setActiveConversationId("");
        setIsMobileOpen(false);
        setNewConversationVersion((current) => current + 1);
        router.push("/");
      },
      toggleCollapse: () => setIsCollapsed((current) => !current),
    }),
    [
      activeConversationId,
      conversations,
      isCollapsed,
      isLoadingConversations,
      isMobileOpen,
      newConversationVersion,
      pathname,
      refreshConversations,
      router,
    ],
  );

  return (
    <SidebarContext.Provider value={value}>
      <div className="flex h-screen w-full overflow-hidden bg-white text-foreground">
        {children}
      </div>
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
