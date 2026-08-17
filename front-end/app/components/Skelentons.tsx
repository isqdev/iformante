"use client";

import {Skeleton} from "@/components/ui/skeleton";

export function ChatSkeleton() {
  return (
    <div
      aria-label="Carregando conversa"
      className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-8 md:px-6"
    >
      <div className="ml-auto flex w-2/3 flex-col items-end gap-2">
        <Skeleton className="h-12 w-full rounded-2xl" />
      </div>

      <div className="flex w-full max-w-2xl flex-col gap-3">
        <Skeleton className="h-4 w-full rounded-sm" />
        <Skeleton className="h-4 w-11/12 rounded-sm" />
        <Skeleton className="h-4 w-3/4 rounded-sm" />
      </div>

      <div className="ml-auto flex w-1/2 flex-col items-end gap-2">
        <Skeleton className="h-12 w-full rounded-2xl" />
      </div>

      <div className="flex w-full max-w-2xl flex-col gap-3">
        <Skeleton className="h-4 w-full rounded-sm" />
        <Skeleton className="h-4 w-4/5 rounded-sm" />
      </div>
    </div>
  );
}

export function SidebarSkeleton() {
  return (
    <div aria-label="Carregando conversas" className="flex flex-col gap-1">
      {Array.from({length: 16}, (_, index) => (
        <Skeleton key={index} className="h-8 w-full rounded-lg" />
      ))}
    </div>
  );
}
