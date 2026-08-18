"use client";

import {useState} from "react";

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
  const sidebar = useSidebar();
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isDocumentOpen, setIsDocumentOpen] = useState(false);

  return (
    <>
      <Sidebar
        activeConversationId={sidebar.activeConversationId}
        conversations={sidebar.conversations}
        currentUser={currentUser}
        isLoadingConversations={sidebar.isLoadingConversations}
        isNewConversationActive={sidebar.isNewConversationActive}
        onOpenDocuments={sidebar.openDocuments}
        onNewDocument={() => setIsDocumentOpen(true)}
        onNewConversation={sidebar.startNewConversation}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onSelectConversation={sidebar.selectConversation}
      />

      <DocumentModal open={isDocumentOpen} onOpenChange={setIsDocumentOpen} />
      <SettingsModal
        open={isSettingsOpen}
        user={currentUser}
        onOpenChange={setIsSettingsOpen}
      />
    </>
  );
}
