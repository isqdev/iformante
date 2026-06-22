"use client";

import {Button, Skeleton} from "@heroui/react";
import {LayoutSideContentLeft} from "@gravity-ui/icons";

type ChatHeaderProps = {
  isLoading?: boolean;
  title: string;
  onOpenMobileSidebar: () => void;
};

export function ChatHeader({isLoading = false, title, onOpenMobileSidebar}: ChatHeaderProps) {
  return (
    <header className="relative flex h-14 items-center justify-center border-b px-4 md:px-6">
      <Button
        isIconOnly
        aria-label="Abrir menu lateral"
        className="absolute left-4 md:hidden"
        size="sm"
        variant="ghost"
        onPress={onOpenMobileSidebar}
      >
        <LayoutSideContentLeft className="h-4 w-4" />
      </Button>

      {isLoading ? (
        <Skeleton aria-label="Carregando titulo da conversa" className="h-4 w-40 rounded-sm" />
      ) : title ? (
        <span className="truncate text-sm font-medium">
          {title}
        </span>
      ) : null}
    </header>
  );
}
