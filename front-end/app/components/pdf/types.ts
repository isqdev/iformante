export type PdfAnchor = {
  page: number;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
};
export type PdfCitation = { chunk_id: string; anchors: PdfAnchor[] };
