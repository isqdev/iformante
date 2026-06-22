export type MessageSource = {
  filename: string;
  url: string;
};

export type Message = {
  id: string;
  role: "assistant" | "user";
  content: string;
  isStreaming?: boolean;
  sources?: MessageSource[];
};
