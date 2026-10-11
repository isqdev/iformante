"use client";

import { useChatConversation } from "../hooks/useChatConversation";
import { cn } from "@/lib/utils";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";

import { ChatInput } from "../components/ChatInput";
import { ChatHeader } from "../components/ChatHeader";
import { ChatWelcome } from "../components/ChatWelcome";
import { ChatMessages } from "../components/ChatMessages";
import { PdfViewer } from "../components/PdfViewer";
import { DocumentPreview } from "../components/DocumentPreview";
import { PageContainer } from "../components/PageContainer";
import { ChatSkeleton } from "../components/Skelentons";

type ChatAppProps = {
  conversationId?: string;
};

export function ChatApp({ conversationId }: ChatAppProps) {
  const {
    activeConversation,
    chatMessages,
    draft,
    setDraft,
    isStreamingResponse,
    selectedSource,
    setSelectedSource,
    isDesktopLayout,
    shouldShowConversationSkeleton,
    canSend,
    newConversationVersion,
    handleSendMessage,
  } = useChatConversation(conversationId);

  const chatContent = (
    <PageContainer
      className={cn("mr-2", isDesktopLayout && selectedSource && "md:mr-1")}
    >
      <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-transparent!">
        <ChatHeader
          isLoading={shouldShowConversationSkeleton}
          title={activeConversation?.title ?? ""}
        />

        <section className="relative flex min-h-0 flex-1 flex-col">
          {shouldShowConversationSkeleton ? (
            <ChatSkeleton />
          ) : chatMessages.length > 0 ? (
            <>
              <ChatMessages
                messages={chatMessages}
                onOpenSource={setSelectedSource}
              />

              <div className="pointer-events-none absolute inset-x-0 bottom-0 px-4 py-4 md:px-6">
                <div className="pointer-events-auto">
                  <ChatInput
                    canSend={canSend}
                    draft={draft}
                    focusKey={`${conversationId ?? "new"}:${newConversationVersion}`}
                    isStreaming={isStreamingResponse}
                    onDraftChange={setDraft}
                    onSend={handleSendMessage}
                  />
                </div>
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center px-4 py-8 md:px-6">
              <div className="w-full max-w-3xl -translate-y-8 md:-translate-y-12">
                <ChatWelcome key={newConversationVersion} />

                <ChatInput
                  canSend={canSend}
                  draft={draft}
                  focusKey={`${conversationId ?? "new"}:${newConversationVersion}`}
                  isStreaming={isStreamingResponse}
                  onDraftChange={setDraft}
                  onSend={handleSendMessage}
                />
              </div>
            </div>
          )}
        </section>
      </main>
    </PageContainer>
  );

  if (isDesktopLayout && selectedSource) {
    return (
      <ResizablePanelGroup orientation="horizontal">
        <ResizablePanel defaultSize="58%" minSize="40%">
          {chatContent}
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize="42%" minSize="30%">
          <PageContainer className="ml-1 mr-2 md:ml-1">
            <PdfViewer
              key={selectedSource.document_id}
              filename={selectedSource.filename}
              citations={selectedSource.citations}
              url={`/api/documents/${encodeURIComponent(selectedSource.document_id)}/content`}
              onClose={() => setSelectedSource(null)}
            />
          </PageContainer>
        </ResizablePanel>
      </ResizablePanelGroup>
    );
  }

  return (
    <>
      {chatContent}
      <DocumentPreview
        document={
          selectedSource
            ? {
                id: selectedSource.document_id,
                name: selectedSource.filename,
                source_type: selectedSource.source_type ?? "PDF",
                url: selectedSource.url ?? null,
                citations: selectedSource.citations,
              }
            : null
        }
        onClose={() => setSelectedSource(null)}
      />
    </>
  );
}
