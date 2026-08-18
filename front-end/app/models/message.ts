export type MessageSource = {
  document_id: string;
  filename: string;
  url: string | null;
  source_type?: "PDF" | "WEB_PAGE";
};

export type Message = {
  id: string;
  role: "assistant" | "user";
  content: string;
  isStreaming?: boolean;
  usesRag?: boolean;
  sources?: MessageSource[];
};
