export type Message = {
  id: string;
  role: "assistant" | "user";
  content: string;
  isStreaming?: boolean;
};
