import type { PreviewDocument } from "../DocumentPreview";
export type DocumentItem = PreviewDocument & {
  status?: "PENDING" | "PROCESSING" | "INDEXED" | "ERROR";
  uploaded_by_name?: string;
};
