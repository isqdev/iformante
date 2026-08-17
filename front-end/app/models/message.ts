export type MessageSource = {
  document_id: string;
  filename: string;
  url: string;
};

export type Message = {
  id: string;
  role: "assistant" | "user";
  content: string;
  isStreaming?: boolean;
  usesRag?: boolean;
  sources?: MessageSource[];
};
