"use client";

import {useCallback, useEffect, useState} from "react";
import {ArrowUpRightFromSquare, TrashBin} from "@gravity-ui/icons";
import {Button, Spinner, Toast} from "@heroui/react";

import {useSidebar} from "../../components/sidebar/SidebarProvider";

type DocumentItem = {
  id: string;
  name: string;
  url: string;
};

export function DocumentsPage() {
  const {openMobileSidebar} = useSidebar();
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
      Toast.toast.danger(
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
        throw new Error(payload?.error ?? "Não foi possível excluir o documento.");
      }

      setDocuments((current) => current.filter((item) => item.id !== documentId));
      Toast.toast.success("Documento excluído com sucesso.");
    } catch (error) {
      Toast.toast.danger(
        error instanceof Error ? error.message : "Não foi possível excluir o documento.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <main className="min-w-0 flex-1 overflow-auto bg-white">
      <header className="flex h-14 items-center border-b px-4 md:px-6">
        <Button
          isIconOnly
          aria-label="Abrir menu lateral"
          className="mr-3 md:hidden"
          size="sm"
          variant="ghost"
          onPress={openMobileSidebar}
        >
          <span aria-hidden>☰</span>
        </Button>
        <h1 className="text-lg font-semibold">Documentos</h1>
      </header>

      <section className="p-4 md:p-6">
        <div className="overflow-hidden rounded-xl border border-separator">
          <table className="w-full table-fixed text-left">
            <thead className="bg-default-50 text-sm text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">Nome</th>
                <th className="w-28 px-4 py-3 text-right font-medium">Ações</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td className="px-4 py-10 text-center" colSpan={2}><Spinner size="sm" /></td></tr>
              ) : documents.length === 0 ? (
                <tr><td className="px-4 py-10 text-center text-sm text-muted" colSpan={2}>Nenhum documento encontrado.</td></tr>
              ) : documents.map((document) => (
                <tr key={document.id} className="border-t border-separator">
                  <td className="truncate px-4 py-3 text-sm">{document.name}</td>
                  <td className="px-4 py-2">
                    <div className="flex justify-end gap-1">
                      <Button
                        isIconOnly
                        aria-label={`Abrir ${document.name}`}
                        size="sm"
                        variant="ghost"
                        onPress={() => window.open(document.url, "_blank", "noopener,noreferrer")}
                      >
                        <ArrowUpRightFromSquare className="h-4 w-4" />
                      </Button>
                      <Button
                        isIconOnly
                        aria-label={`Excluir ${document.name}`}
                        className="text-danger"
                        isDisabled={deletingId === document.id}
                        size="sm"
                        variant="ghost"
                        onPress={() => void deleteDocument(document.id)}
                      >
                        {deletingId === document.id ? <Spinner size="sm" /> : <TrashBin className="h-4 w-4" />}
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
