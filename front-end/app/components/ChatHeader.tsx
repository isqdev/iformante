"use client";

import {SidebarTrigger} from "@/components/ui/sidebar";
import {Skeleton} from "@/components/ui/skeleton";
import {ThemeToggle} from "./ThemeToggle";

type ChatHeaderProps = {
  isLoading?: boolean;
  title: string;
};

export function ChatHeader({isLoading = false, title}: ChatHeaderProps) {
  return (
    <header className="relative flex h-14 shrink-0 items-center justify-center border-b px-4 md:px-6">
      <SidebarTrigger
        aria-label="Abrir menu lateral"
        className="absolute left-4"
      />

      {isLoading ? (
        <Skeleton aria-label="Carregando titulo da conversa" className="h-4 w-40 rounded-sm" />
      ) : title ? (
        <span className="truncate text-sm font-medium">
          {title}
        </span>
      ) : null}

      <div className="absolute right-4">
        <ThemeToggle />
      </div>
    </header>
  );
}
