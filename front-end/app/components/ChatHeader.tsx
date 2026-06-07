"use client";

import {Button} from "@heroui/react";
import {LayoutSideContentLeft} from "@gravity-ui/icons";

type ChatHeaderProps = {
  title: string;
  onOpenMobileSidebar: () => void;
};

export function ChatHeader({title, onOpenMobileSidebar}: ChatHeaderProps) {
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

      <span className="truncate text-sm font-medium">
        {title}
      </span>
    </header>
  );
}
