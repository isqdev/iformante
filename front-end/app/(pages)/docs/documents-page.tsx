"use client";

import {useCallback, useEffect, useState} from "react";
import {ArrowUpRightFromSquare, TrashBin} from "@gravity-ui/icons";
import {toast} from "sonner";
import {Button} from "@/components/ui/button";
import {Card} from "@/components/ui/card";
import {SidebarTrigger} from "@/components/ui/sidebar";
import {Spinner} from "@/components/ui/spinner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type DocumentItem = {
  id: string;
  name: string;
  url: string;
};

export function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const loadDocuments = useCallback(async () => {
    setIsLoading(true);

    try {
      const response = await fetch("/api/documents", {cache: "no-store"});
      const payload = (await response.json().catch(() => null)) as
        | DocumentItem[]
        | {error?: string}
        | null;

      if (!response.ok || !Array.isArray(payload)) {
        throw new Error(!Array.isArray(payload) ? payload?.error : undefined);
      }

      setDocuments(payload);
    } catch (error) {
      toast.error(
        error instanceof Error && error.message
          ? error.message
          : "Não foi possível carregar os documentos.",
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => void loadDocuments());
  }, [loadDocuments]);

  async function deleteDocument(documentId: string) {
    if (deletingId) return;
    setDeletingId(documentId);

    try {
      const response = await fetch(`/api/documents/${documentId}`, {
        method: "DELETE",
      });
      const payload = (await response.json().catch(() => null)) as
        | {error?: string}
        | null;

      if (!response.ok) {
        throw new Error(
          payload?.error ?? "Não foi possível excluir o documento.",
        );
      }

      setDocuments((current) =>
        current.filter((item) => item.id !== documentId),
      );
      toast.success("Documento excluído com sucesso.");
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Não foi possível excluir o documento.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <Card className="m-2 h-[calc(100%-1rem)] min-w-0 gap-0 overflow-auto rounded-lg border border-sidebar-border bg-sidebar py-0 shadow-sm ring-0">
      <header className="flex h-14 items-center border-b px-4 md:px-6">
        <SidebarTrigger
          aria-label="Abrir menu lateral"
          className="mr-3"
        />
        <h1 className="text-lg font-semibold">Documentos</h1>
      </header>

      <section className="p-4 md:p-6">
        <div className="overflow-hidden rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nome</TableHead>
                <TableHead className="w-28 text-right">Ações</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell className="h-24 text-center" colSpan={2}>
                    <Spinner aria-label="Carregando documentos" />
                  </TableCell>
                </TableRow>
              ) : documents.length === 0 ? (
                <TableRow>
                  <TableCell
                    className="h-24 text-center text-muted-foreground"
                    colSpan={2}
                  >
                    Nenhum documento encontrado.
                  </TableCell>
                </TableRow>
              ) : (
                documents.map((document) => (
                  <TableRow key={document.id}>
                    <TableCell className="max-w-0 truncate">
                      {document.name}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          aria-label={`Abrir ${document.name}`}
                          size="icon-sm"
                          variant="ghost"
                          onClick={() =>
                            window.open(
                              document.url,
                              "_blank",
                              "noopener,noreferrer",
                            )
                          }
                        >
                          <ArrowUpRightFromSquare />
                        </Button>
                        <Button
                          aria-label={`Excluir ${document.name}`}
                          disabled={deletingId === document.id}
                          size="icon-sm"
                          variant="destructive"
                          onClick={() => void deleteDocument(document.id)}
                        >
                          {deletingId === document.id ? (
                            <Spinner />
                          ) : (
                            <TrashBin />
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </section>
    </Card>
  );
}
