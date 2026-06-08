import {ChatApp} from "../../chat-app";

type ConversationPageProps = {
  params: Promise<{
    conversationId: string;
  }>;
};

export default async function ConversationPage({params}: ConversationPageProps) {
  const {conversationId} = await params;

  return <ChatApp conversationId={conversationId} />;
}
