"use client";

import {useSyncExternalStore} from "react";
import {Toast, useOverlayState} from "@heroui/react";

import {DocumentModal} from "../DocumentModal";
import {SettingsModal} from "../SettingsModal";
import {Sidebar} from "./Sidebar";
import {useSidebar} from "./SidebarProvider";
import type {User} from "../../models/user";

const currentUser: User = {
  name: "Isaque Dias",
  role: "Discente",
};

export function AppSidebar() {
  const isMounted = useSyncExternalStore(
    () => () => undefined,
    () => true,
    () => false,
  );
  const sidebar = useSidebar();
  const settingsModal = useOverlayState();
  const documentModal = useOverlayState();

  if (!isMounted) {
    return null;
  }

  return (
    <>
      <Sidebar
        activeConversationId={sidebar.activeConversationId}
        conversations={sidebar.conversations}
        currentUser={currentUser}
        isCollapsed={sidebar.isCollapsed}
        isLoadingConversations={sidebar.isLoadingConversations}
        isMobileOpen={sidebar.isMobileOpen}
        isNewConversationActive={sidebar.isNewConversationActive}
        onCloseMobile={sidebar.closeMobileSidebar}
        onNewDocument={documentModal.open}
        onNewConversation={sidebar.startNewConversation}
        onOpenSettings={settingsModal.open}
        onSelectConversation={sidebar.selectConversation}
        onToggleCollapse={sidebar.toggleCollapse}
      />

      <DocumentModal state={documentModal} />
      <SettingsModal state={settingsModal} user={currentUser} />
      <Toast.Provider placement="top end" />
    </>
  );
}
