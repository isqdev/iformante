import {DocumentsPage} from "../documents-page";

export default async function DocumentPage({params}: {params: Promise<{documentId: string}>}) {
  const {documentId} = await params;
  return <DocumentsPage documentId={documentId} />;
}
