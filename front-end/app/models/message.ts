import type {PdfCitation} from "../components/pdf/types";
export type MessageSource = {
  citations?: PdfCitation[];
  document_id: string;
  filename: string;
  url: string | null;
  source_type?: "PDF" | "WEB_PAGE";
};

export type Message = {
  response_mode?: "text" | "speech";
  playback_status?: "pending" | "completed" | "interrupted" | "failed" | null;
  id: string;
  role: "assistant" | "user";
  content: string;
  isStreaming?: boolean;
  usesRag?: boolean;
  sources?: MessageSource[];
};
