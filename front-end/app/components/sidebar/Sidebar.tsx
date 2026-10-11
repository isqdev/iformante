"use client";

import {FilePlus, FileText, Pencil} from "@gravity-ui/icons";
import {Phone} from "lucide-react";
import {BrandLogo} from "../BrandLogo";
import {Avatar, AvatarFallback} from "@/components/ui/avatar";
import {Skeleton} from "@/components/ui/skeleton";
import {
  Sidebar as UiSidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  useSidebar as useUiSidebar,
} from "@/components/ui/sidebar";

import type {Conversation} from "../../models/conversation";
import type {User} from "../../models/user";

type SidebarProps = {
  activeConversationId: string;
  conversations: Conversation[];
  currentUser: User | null;
  isLoadingUser: boolean;
  isLoadingConversations: boolean;
  isNewConversationActive: boolean;
  onOpenDocuments: () => void;
  onOpenCall: () => void;
  isCallActive: boolean;
  onNewDocument: () => void;
  onNewConversation: () => void;
  onOpenSettings: () => void;
  onSelectConversation: (conversationId: string) => void;
};

export function Sidebar({
  activeConversationId,
  conversations,
  currentUser,
  isLoadingUser,
  isLoadingConversations,
  isNewConversationActive,
  onOpenDocuments,
  onOpenCall,
  isCallActive,
  onNewDocument,
  onNewConversation,
  onOpenSettings,
  onSelectConversation,
}: SidebarProps) {
  const {setOpenMobile} = useUiSidebar();

  function runAndCloseMobile(action: () => void) {
    action();
    setOpenMobile(false);
  }

  return (
    <UiSidebar className="backdrop-blur-xl" collapsible="icon" variant="floating">
      <SidebarHeader className="h-14 justify-center">
        <div className="flex items-center gap-2 px-2 group-data-[collapsible=icon]:justify-center">
          <BrandLogo className="size-8" />
          <span className="font-semibold group-data-[collapsible=icon]:hidden">
            InFormante
          </span>
        </div>
      </SidebarHeader>

      <SidebarContent className="group-data-[collapsible=icon]:items-center">
        <SidebarGroup className="group-data-[collapsible=icon]:w-auto group-data-[collapsible=icon]:p-0">
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton isActive={isCallActive} tooltip="Chamada" onClick={() => runAndCloseMobile(onOpenCall)}>
                  <Phone />
                  <span>Chamada</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              <SidebarMenuItem>
                <SidebarMenuButton
                  isActive={isNewConversationActive}
                  tooltip="Nova conversa"
                  onClick={() => runAndCloseMobile(onNewConversation)}
                >
                  <Pencil />
                  <span>Nova conversa</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              {currentUser?.role === "ADMIN" && (              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip="Novo documento"
                  onClick={() => runAndCloseMobile(onNewDocument)}
                >
                  <FilePlus />
                  <span>Novo documento</span>
                </SidebarMenuButton>
              </SidebarMenuItem>)}
              <SidebarMenuItem>
                <SidebarMenuButton
                  tooltip="Documentos"
                  onClick={() => runAndCloseMobile(onOpenDocuments)}
                >
                  <FileText />
                  <span>Documentos</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {currentUser && (        <SidebarGroup className="group-data-[collapsible=icon]:hidden">
          <SidebarGroupLabel>Recentes</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu className="gap-1">
              {isLoadingConversations
                ? Array.from({length: 16}, (_, index) => (
                    <SidebarMenuItem key={index}>
                      <SidebarMenuSkeleton className="p-0 [&_[data-sidebar=menu-skeleton-text]]:h-8 [&_[data-sidebar=menu-skeleton-text]]:max-w-none" />
                    </SidebarMenuItem>
                  ))
                : conversations.map((conversation) => (
                    <SidebarMenuItem key={conversation.id}>
                      <SidebarMenuButton
                        isActive={conversation.id === activeConversationId}
                        tooltip={conversation.title}
                        onClick={() =>
                          runAndCloseMobile(() =>
                            onSelectConversation(conversation.id),
                          )
                        }
                      >
                        <span>{conversation.title}</span>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>)}
      </SidebarContent>

      <SidebarFooter className="group-data-[collapsible=icon]:items-center">
        <SidebarMenu className="group-data-[collapsible=icon]:w-8">
          <SidebarMenuItem>
            {isLoadingUser ? (
              <div role="status" aria-label="Verificando sessão" className="flex h-12 items-center gap-2 px-2">
                <Skeleton className="size-8 shrink-0 rounded-full" />
                <Skeleton className="h-4 w-20 group-data-[collapsible=icon]:hidden" />
              </div>
            ) : (
            <SidebarMenuButton
              size="lg"
              tooltip={currentUser?.first_name ?? "Entrar"}
              onClick={() => runAndCloseMobile(onOpenSettings)}
            >
              <Avatar>
                <AvatarFallback>
                  {currentUser?.first_name.slice(0, 2).toUpperCase() ?? "IF"}
                </AvatarFallback>
              </Avatar>
              <span>{currentUser?.first_name ?? "Entrar"}</span>
            </SidebarMenuButton>
            )}
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </UiSidebar>
  );
}
