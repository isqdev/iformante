"use client";

import {ChatHeader} from "../../../components/ChatHeader";
import {ChatSkeleton} from "../../../components/Skelentons";
import {useSidebar} from "../../../components/sidebar/SidebarProvider";

export default function ConversationLoading() {
  const {openMobileSidebar} = useSidebar();

  return (
    <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-white">
      <ChatHeader isLoading title="" onOpenMobileSidebar={openMobileSidebar} />

      <section className="flex min-h-0 flex-1 flex-col">
        <ChatSkeleton />
      </section>
    </main>
  );
}
