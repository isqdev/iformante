"use client";

import {useCallback, useState} from "react";
import {usePathname, useRouter} from "next/navigation";
import {useAuth} from "../auth/AuthProvider";
import {isAdmin} from "@/lib/permissions";

import {DropOverlay} from "../documents/DropOverlay";
import {useDocumentDrop, type DroppedSource} from "../documents/useDocumentDrop";
import {DocumentModal} from "../DocumentModal";
import {SettingsModal} from "../SettingsModal";
import {Sidebar} from "./Sidebar";
import {useSidebar} from "./SidebarProvider";

export function AppSidebar() {
  const {user: currentUser, loading: isLoadingUser} = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const sidebar = useSidebar();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDocumentOpen, setIsDocumentOpen] = useState(false);

  const [initialSource, setInitialSource] = useState<DroppedSource | null>(null);
  const acceptDrop = useCallback((source: DroppedSource) => {setInitialSource(source); setIsDocumentOpen(true);}, []);
  const recognized = useDocumentDrop(isAdmin(currentUser), acceptDrop);

  return (
    <>
      <Sidebar
        activeConversationId={sidebar.activeConversationId}
        conversations={sidebar.conversations}
        currentUser={currentUser}
        isLoadingUser={isLoadingUser}
        isLoadingConversations={sidebar.isLoadingConversations}
        isNewConversationActive={sidebar.isNewConversationActive}
        onOpenDocuments={sidebar.openDocuments}
        onOpenCall={() => router.push("/call")}
        isCallActive={pathname === "/call"}
        onOpenSystem={() => router.push("/system")}
        isSystemActive={pathname === "/system"}
        onNewDocument={() => {setInitialSource(null); setIsDocumentOpen(true);}}
        onNewConversation={sidebar.startNewConversation}
        onOpenSettings={() => currentUser ? setIsSettingsOpen(true) : router.push("/login")}
        onSelectConversation={sidebar.selectConversation}
      />

      {recognized && <DropOverlay />}
      {isAdmin(currentUser) && <DocumentModal initialSource={initialSource} open={isDocumentOpen} onOpenChange={setIsDocumentOpen} />}
      {currentUser && <SettingsModal
        open={isSettingsOpen}
        user={currentUser}
        onOpenChange={setIsSettingsOpen}
      />}
    </>
  );
}
