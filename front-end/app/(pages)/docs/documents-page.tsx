"use client";

import {useCallback, useEffect, useState} from "react";
import {useRouter} from "next/navigation";
import {Ellipsis, FileText, Globe, Pencil, Trash2} from "lucide-react";
import {toast} from "sonner";
import {Button} from "@/components/ui/button";
import {Card, CardHeader, CardTitle} from "@/components/ui/card";
import {Dialog, DialogContent, DialogDescription, DialogTitle} from "@/components/ui/dialog";
import {Input} from "@/components/ui/input";
import {Popover, PopoverClose, PopoverContent, PopoverTrigger} from "@/components/ui/popover";
import {SidebarTrigger} from "@/components/ui/sidebar";
import {Spinner} from "@/components/ui/spinner";
import {cn} from "@/lib/utils";
import {DocumentDialogPreview, type PreviewDocument} from "../../components/DocumentPreview";
import {PageContainer} from "../../components/PageContainer";

type DocumentItem = PreviewDocument & {status: "PENDING" | "PROCESSING" | "INDEXED" | "ERROR"; uploaded_by_name: string};

export function DocumentsPage({documentId}: {documentId?: string}) {
  const router = useRouter();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [renamingDocument, setRenamingDocument] = useState<DocumentItem | null>(null);
  const [title, setTitle] = useState("");
  const loadDocuments = useCallback(async () => { setIsLoading(true); try { const response = await fetch("/api/documents", {cache: "no-store"}); const payload = await response.json().catch(() => null); if (!response.ok || !Array.isArray(payload)) throw new Error(payload?.error); setDocuments(payload); } catch (error) { toast.error(error instanceof Error && error.message ? error.message : "Não foi possível carregar os documentos."); } finally { setIsLoading(false); } }, []);
  useEffect(() => { queueMicrotask(() => void loadDocuments()); window.addEventListener("documents:changed", loadDocuments); return () => window.removeEventListener("documents:changed", loadDocuments); }, [loadDocuments]);
  const selectedDocument = documents.find((document) => document.id === documentId) ?? null;
  function openDocument(document: DocumentItem) { if (document.source_type === "WEB_PAGE" && document.url) { window.open(document.url, "_blank", "noopener,noreferrer"); return; } router.push(`/docs/${document.id}`); }
  async function deleteDocument(document: DocumentItem) { try { const response = await fetch(`/api/documents/${document.id}`, {method: "DELETE"}); const payload = await response.json().catch(() => null); if (!response.ok) throw new Error(payload?.error); setDocuments((current) => current.filter((item) => item.id !== document.id)); if (document.id === documentId) router.push("/docs"); toast.success("Documento excluído com sucesso."); } catch (error) { toast.error(error instanceof Error && error.message ? error.message : "Não foi possível excluir o documento."); } }
  async function renameDocument() { if (!renamingDocument || !title.trim()) return; try { const response = await fetch(`/api/documents/${renamingDocument.id}`, {method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({title: title.trim()})}); const payload = await response.json().catch(() => null); if (!response.ok) throw new Error(payload?.error); setDocuments((current) => current.map((item) => item.id === renamingDocument.id ? payload : item)); toast.success("Documento renomeado."); setRenamingDocument(null); } catch (error) { toast.error(error instanceof Error && error.message ? error.message : "Não foi possível renomear o documento."); } }
  function statusLabel(status: DocumentItem["status"]) { return ({PENDING: "Pendente", PROCESSING: "Processando", INDEXED: "Indexado", ERROR: "Erro"})[status]; }
  function statusClass(status: DocumentItem["status"]) { return ({PENDING: "bg-[var(--document-status-pending)] text-foreground", PROCESSING: "bg-[var(--document-status-processing)] text-foreground", INDEXED: "bg-[var(--document-status-indexed)] text-foreground", ERROR: "bg-destructive/15 text-destructive"})[status]; }
  return <PageContainer><header className="flex h-14 shrink-0 items-center border-b px-4 md:px-6"><SidebarTrigger aria-label="Abrir menu lateral" className="mr-3" /><h1 className="text-lg font-semibold">Documentos</h1></header><section className="min-h-0 flex-1 overflow-auto p-4 md:p-6">{isLoading ? <div className="flex h-24 items-center justify-center"><Spinner aria-label="Carregando documentos" /></div> : documents.length === 0 ? <p className="py-12 text-center text-muted-foreground">Nenhum documento encontrado.</p> : <div className="flex flex-col gap-3">{documents.map((document) => <Card key={document.id} className="gap-0 py-0"><CardHeader className="flex flex-row items-center gap-3 px-4 py-3"><div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">{document.source_type === "PDF" ? <FileText /> : <Globe />}</div><div className="min-w-0 flex-1"><CardTitle><button className="max-w-full truncate text-left hover:underline" onClick={() => openDocument(document)}>{document.name}</button></CardTitle><p className="mt-1 text-sm text-muted-foreground">Adicionado por {document.uploaded_by_name}</p></div><div className="flex shrink-0 items-center gap-2"><span className="inline-flex h-6 items-center rounded-full bg-muted px-2 text-xs text-muted-foreground">{document.source_type === "PDF" ? "PDF" : "Página Web"}</span><span className={cn("inline-flex h-6 items-center rounded-full px-2 text-xs font-medium", statusClass(document.status))}>{statusLabel(document.status)}</span><DocumentActions document={document} onDelete={deleteDocument} onOpen={openDocument} onRename={(item) => { setTitle(item.name); setRenamingDocument(item); }} /></div></CardHeader></Card>)}</div>}</section><DocumentDialogPreview document={selectedDocument} onClose={() => router.push("/docs")} /><Dialog open={Boolean(renamingDocument)} onOpenChange={(open) => { if (!open) setRenamingDocument(null); }}><DialogContent><DialogTitle>Renomear documento</DialogTitle><DialogDescription>Escolha um novo título para este documento.</DialogDescription><Input value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") void renameDocument(); }} /><Button onClick={() => void renameDocument()}>Salvar</Button></DialogContent></Dialog></PageContainer>;
}

function DocumentActions({document, onDelete, onOpen, onRename}: {document: DocumentItem; onDelete: (document: DocumentItem) => Promise<void>; onOpen: (document: DocumentItem) => void; onRename: (document: DocumentItem) => void}) {
  return <Popover><PopoverTrigger render={<Button aria-label={`Ações para ${document.name}`} size="icon-sm" variant="ghost"><Ellipsis /></Button>} /><PopoverContent><PopoverClose render={<Button className="justify-start" variant="ghost" onClick={() => onOpen(document)}>Abrir</Button>} /><PopoverClose render={<Button className="justify-start" variant="ghost" onClick={() => onRename(document)}><Pencil data-icon="inline-start" />Renomear</Button>} /><PopoverClose render={<Button className="justify-start" variant="ghost" onClick={() => void onDelete(document)}><Trash2 data-icon="inline-start" />Excluir</Button>} /></PopoverContent></Popover>;
}
