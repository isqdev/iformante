"use client";

import {ChatHeader} from "../../../components/ChatHeader";
import {ChatSkeleton} from "../../../components/Skelentons";

export default function ConversationLoading() {
  return (
    <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-background">
      <ChatHeader isLoading title="" />

      <section className="flex min-h-0 flex-1 flex-col">
        <ChatSkeleton />
      </section>
    </main>
  );
}
