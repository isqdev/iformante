"use client";

import {FaceRobot, FilePlus, LayoutSideContentLeft, Pencil} from "@gravity-ui/icons";
import {Avatar, Button, ScrollShadow} from "@heroui/react";

import type {Conversation} from "../models/conversation";
import type {User} from "../models/user";

type SidebarProps = {
  activeConversationId: string;
  conversations: Conversation[];
  currentUser: User;
  isCollapsed: boolean;
  isMobileOpen: boolean;
  isNewConversationActive: boolean;
  onCloseMobile: () => void;
  onNewDocument: () => void;
  onNewConversation: () => void;
  onOpenSettings: () => void;
  onSelectConversation: (conversationId: string) => void;
  onToggleCollapse: () => void;
};

export function Sidebar({
  activeConversationId,
  conversations,
  currentUser,
  isCollapsed,
  isMobileOpen,
  isNewConversationActive,
  onCloseMobile,
  onNewDocument,
  onNewConversation,
  onOpenSettings,
  onSelectConversation,
  onToggleCollapse,
}: SidebarProps) {
  const desktopWidthClass = isCollapsed ? "md:w-14" : "md:w-[280px]";
  const labelState = isCollapsed
    ? "md:pointer-events-none md:w-0 md:-translate-x-2 md:opacity-0"
    : "opacity-100";

  return (
    <>
      {isMobileOpen ? (
        <button
          aria-label="Fechar menu lateral"
          className="fixed inset-0 z-30 bg-backdrop md:hidden"
          onClick={onCloseMobile}
          type="button"
        />
      ) : null}

      <div className={"hidden shrink-0 transition-[width] duration-300 ease-out md:block " + desktopWidthClass}>
        <div className="relative h-full">
          <aside className="chat-sidebar flex h-full flex-col border-r border-separator bg-white">
            <div
              className={"flex h-14 items-center px-4 " + (isCollapsed ? "md:justify-center md:px-0" : "")}
            >
              <FaceRobot className="h-5 w-5 shrink-0" />
              <span
                className={"min-w-0 overflow-hidden whitespace-nowrap text-sm font-semibold transition-[opacity,transform,width,padding] duration-200 " + (isCollapsed ? "md:pl-0" : "pl-2") + " " + labelState}
              >
                IFormante
              </span>
            </div>

            <div
              className={"space-y-1 px-3 pb-4 pt-3 transition-[padding] duration-300 " + (isCollapsed ? "md:flex md:flex-col md:items-center md:px-0" : "")}
            >
              <Button
                fullWidth
                className={"justify-start text-foreground " + (isCollapsed ? "md:h-10 md:w-10 md:min-w-10 md:justify-center md:px-0" : "")}
                size="sm"
                variant={isNewConversationActive ? "tertiary" : "ghost"}
                onPress={onNewConversation}
              >
                <span
                  className={"flex min-w-0 items-center gap-2 " + (isCollapsed ? "md:w-full md:justify-center md:gap-0" : "")}
                >
                  <Pencil className="h-4 w-4 shrink-0" />
                  <span
                    className={"overflow-hidden whitespace-nowrap text-sm transition-[opacity,transform,width] duration-200 " + labelState}
                  >
                    Nova conversa
                  </span>
                </span>
              </Button>

              <Button
                fullWidth
                className={"justify-start text-foreground " + (isCollapsed ? "md:h-10 md:w-10 md:min-w-10 md:justify-center md:px-0" : "")}
                size="sm"
                variant="ghost"
                onPress={onNewDocument}
              >
                <span
                  className={"flex min-w-0 items-center gap-2 " + (isCollapsed ? "md:w-full md:justify-center md:gap-0" : "")}
                >
                  <FilePlus className="h-4 w-4 shrink-0" />
                  <span
                    className={"overflow-hidden whitespace-nowrap text-sm transition-[opacity,transform,width] duration-200 " + labelState}
                  >
                    Novo documento
                  </span>
                </span>
              </Button>
            </div>

            <div
              className={"px-4 pb-2 transition-opacity duration-200 " + (isCollapsed ? "md:pointer-events-none md:hidden md:opacity-0" : "opacity-100")}
            >
              <p className="text-xs font-medium text-muted">Recentes</p>
            </div>

            <ScrollShadow
              className={"min-h-0 flex-1 pb-3 transition-opacity duration-200 " + (isCollapsed ? "px-2 md:pointer-events-none md:hidden md:opacity-0" : "px-3 opacity-100")}
            >
              <div className="space-y-1">
                {conversations.map((conversation) => {
                  const isActive = conversation.id === activeConversationId;

                  return (
                    <Button
                      key={conversation.id}
                      fullWidth
                      className={"justify-start text-foreground " + (isActive ? "font-semibold" : "font-normal")}
                      size="sm"
                      variant={isActive ? "tertiary" : "ghost"}
                      onPress={() => onSelectConversation(conversation.id)}
                    >
                      <span className="truncate text-sm text-foreground">
                        {conversation.title}
                      </span>
                    </Button>
                  );
                })}
              </div>
            </ScrollShadow>

            <div
              className={"mt-auto border-t border-separator py-3 transition-[padding] duration-300 " + (isCollapsed ? "px-2 md:flex md:justify-center md:px-0" : "px-3")}
            >
              <Button
                fullWidth
                className={"justify-start text-foreground " + (isCollapsed ? "md:h-10 md:w-10 md:min-w-10 md:justify-center md:px-0" : "")}
                size="sm"
                variant="ghost"
                onPress={onOpenSettings}
              >
                <div className="flex min-w-0 items-center gap-3">
                  <Avatar size="sm">
                    <Avatar.Fallback>
                      {currentUser.name.slice(0, 2).toUpperCase()}
                    </Avatar.Fallback>
                  </Avatar>
                  <div
                    className={"min-w-0 overflow-hidden whitespace-nowrap text-left transition-[opacity,transform,width] duration-200 " + labelState}
                  >
                    <p className="truncate text-sm">{currentUser.name}</p>
                  </div>
                </div>
              </Button>
            </div>
          </aside>

          <Button
            isIconOnly
            aria-label={isCollapsed ? "Expandir sidebar" : "Colapsar sidebar"}
            className="absolute -right-10 top-7 z-50 hidden h-9 w-9 min-w-9 -translate-y-1/2 md:inline-flex"
            size="sm"
            variant="ghost"
            onPress={onToggleCollapse}
          >
            <LayoutSideContentLeft className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <aside
        className={"chat-sidebar fixed inset-y-0 left-0 z-40 flex w-70 flex-col border-r border-separator bg-white transition-transform duration-300 ease-out md:hidden " + (isMobileOpen ? "translate-x-0" : "-translate-x-full")}
      >
        <div className="flex h-16 items-center px-4">
          <FaceRobot className="h-5 w-5 shrink-0" />
          <span className="min-w-0 truncate pl-2 text-sm font-semibold">
            IFormante
          </span>

          <Button
            isIconOnly
            aria-label="Fechar sidebar"
            className="ml-auto"
            size="sm"
            variant="ghost"
            onPress={onCloseMobile}
          >
            <LayoutSideContentLeft className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-1 px-3 pb-4 pt-3">
          <Button
            fullWidth
            className="justify-start text-foreground"
            size="sm"
            variant={isNewConversationActive ? "tertiary" : "ghost"}
            onPress={onNewConversation}
          >
            <span className="flex min-w-0 items-center gap-2">
              <Pencil className="h-4 w-4 shrink-0" />
              <span className="overflow-hidden whitespace-nowrap text-sm">
                Nova conversa
              </span>
            </span>
          </Button>

          <Button
            fullWidth
            className="justify-start text-foreground"
            size="sm"
            variant="ghost"
            onPress={onNewDocument}
          >
            <span className="flex min-w-0 items-center gap-2">
              <FilePlus className="h-4 w-4 shrink-0" />
              <span className="overflow-hidden whitespace-nowrap text-sm">
                Novo documento
              </span>
            </span>
          </Button>
        </div>

        <div className="px-4 pb-2">
          <p className="text-xs font-medium text-muted">Recentes</p>
        </div>

        <ScrollShadow className="min-h-0 flex-1 px-3 pb-3">
          <div className="space-y-1">
            {conversations.map((conversation) => {
              const isActive = conversation.id === activeConversationId;

              return (
                <Button
                  key={conversation.id}
                  fullWidth
                  className={"justify-start text-foreground " + (isActive ? "bg-default-200 font-semibold" : "font-normal hover:bg-default-100")}
                  size="sm"
                  variant={isActive ? "tertiary" : "ghost"}
                  onPress={() => onSelectConversation(conversation.id)}
                >
                  <span className="truncate text-sm text-foreground">
                    {conversation.title}
                  </span>
                </Button>
              );
            })}
          </div>
        </ScrollShadow>

        <div className="mt-auto border-t border-separator px-3 py-3">
          <Button
            fullWidth
            className="justify-start text-foreground"
            size="sm"
            variant="ghost"
            onPress={onOpenSettings}
          >
            <div className="flex min-w-0 items-center gap-3">
              <Avatar size="sm">
                <Avatar.Fallback >
                  {currentUser.name.slice(0, 2).toUpperCase()}
                </Avatar.Fallback>
              </Avatar>
              <div className="min-w-0 text-left">
                <p className="truncate text-sm">{currentUser.name}</p>
              </div>
            </div>
          </Button>
        </div>
      </aside>
    </>
  );
}
