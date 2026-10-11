"use client";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { DocumentDialogPreview } from "../../components/DocumentPreview";
import { PageContainer } from "../../components/PageContainer";
import { DocumentCard } from "../../components/documents/DocumentCard";
import { DocumentsSkeleton } from "../../components/documents/DocumentsSkeleton";
import type { DocumentItem } from "../../components/documents/types";
import { useAuth } from "../../components/auth/AuthProvider";
import { useDocumentQuery } from "../../hooks/useDocumentQuery";
export function DocumentsPage() {
  const { user } = useAuth();
  const admin = user?.role === "ADMIN";
  const [documentId, selectDocument] = useDocumentQuery();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [renaming, setRenaming] = useState<DocumentItem | null>(null);
  const [deleting, setDeleting] = useState<DocumentItem | null>(null);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch("/api/documents", { cache: "no-store" });
      const data = await response.json();
      if (!response.ok || !Array.isArray(data))
        throw new Error(data.detail ?? data.error);
      setDocuments(data);
    } catch (e) {
      toast.error(
        e instanceof Error
          ? e.message
          : "Não foi possível carregar documentos.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);
  useEffect(() => {
    queueMicrotask(() => void load());
    window.addEventListener("documents:changed", load);
    return () => window.removeEventListener("documents:changed", load);
  }, [load, user?.id]);
  const selected = documents.find((d) => d.id === documentId) ?? null;
  function open(d: DocumentItem) {
    if (d.source_type === "WEB_PAGE" && d.url)
      window.open(d.url, "_blank", "noopener,noreferrer");
    else selectDocument(d.id);
  }
  async function mutate(method: "DELETE" | "PATCH") {
    const d = method === "DELETE" ? deleting : renaming;
    if (!d || !admin) return;
    setBusy(true);
    try {
      const response = await fetch(
        `/api/documents/${encodeURIComponent(d.id)}`,
        {
          method,
          headers: { "Content-Type": "application/json" },
          body:
            method === "PATCH"
              ? JSON.stringify({ title: title.trim() })
              : undefined,
        },
      );
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? data.error);
      setDeleting(null);
      setRenaming(null);
      await load();
      toast.success(
        method === "DELETE" ? "Documento excluído." : "Documento renomeado.",
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <PageContainer>
      <header className="flex h-14 shrink-0 items-center border-b px-4 md:px-6">
        <SidebarTrigger aria-label="Abrir menu lateral" className="mr-3" />
        <h1 className="text-lg font-semibold">Documentos</h1>
      </header>
      <section className="min-h-0 flex-1 overflow-auto p-4 md:p-6">
        {isLoading ? (
          <DocumentsSkeleton />
        ) : documents.length === 0 ? (
          <p className="py-12 text-center text-muted-foreground">
            Nenhum documento encontrado.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {documents.map((d) => (
              <DocumentCard
                key={d.id}
                document={d}
                admin={admin}
                onOpen={open}
                onRename={(d) => {
                  setTitle(d.name);
                  setRenaming(d);
                }}
                onDelete={setDeleting}
              />
            ))}
          </div>
        )}
      </section>
      <DocumentDialogPreview
        document={selected}
        onClose={() => selectDocument(null)}
      />
      <Dialog
        open={Boolean(renaming)}
        onOpenChange={(o) => {
          if (!o) setRenaming(null);
        }}
      >
        <DialogContent>
          <DialogTitle>Renomear documento</DialogTitle>
          <DialogDescription>Escolha o título do documento.</DialogDescription>
          <Input
            aria-label="Título"
            value={title}
            maxLength={255}
            onChange={(e) => setTitle(e.target.value)}
          />
          <Button
            disabled={busy || !title.trim()}
            onClick={() => mutate("PATCH")}
          >
            Salvar
          </Button>
        </DialogContent>
      </Dialog>
      <Dialog
        open={Boolean(deleting)}
        onOpenChange={(o) => {
          if (!o) setDeleting(null);
        }}
      >
        <DialogContent>
          <DialogTitle>Excluir documento?</DialogTitle>
          <DialogDescription>{deleting?.name}</DialogDescription>
          <Button
            disabled={busy}
            variant="destructive"
            onClick={() => mutate("DELETE")}
          >
            Excluir
          </Button>
          <Button variant="outline" onClick={() => setDeleting(null)}>
            Cancelar
          </Button>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
