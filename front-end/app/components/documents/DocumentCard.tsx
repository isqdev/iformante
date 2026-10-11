import { Ellipsis, FileText, Globe, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { DocumentItem } from "./types";
const labels = {
  PENDING: "Pendente",
  PROCESSING: "Processando",
  INDEXED: "Indexado",
  ERROR: "Erro",
};
export function DocumentCard({
  document,
  admin,
  onOpen,
  onRename,
  onDelete,
}: {
  document: DocumentItem;
  admin: boolean;
  onOpen: (d: DocumentItem) => void;
  onRename: (d: DocumentItem) => void;
  onDelete: (d: DocumentItem) => void;
}) {
  return (
    <Card className="gap-0 py-0">
      <CardHeader className="flex flex-wrap items-center gap-3 px-4 py-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          {document.source_type === "PDF" ? <FileText /> : <Globe />}
        </div>
        <div className="min-w-0 flex-1">
          <CardTitle>
            <button
              className="max-w-full truncate text-left hover:underline"
              onClick={() => onOpen(document)}
            >
              {document.name}
            </button>
          </CardTitle>
          {admin && (
            <p className="mt-1 text-sm text-muted-foreground">
              Adicionado por {document.uploaded_by_name}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-muted px-2 py-1 text-xs">
            {document.source_type === "PDF" ? "PDF" : "Página Web"}
          </span>
          {admin && (
            <>
              <span
                className={`rounded-full px-2 py-1 text-xs ${document.status === "ERROR" ? "bg-destructive/15 text-destructive" : document.status === "INDEXED" ? "bg-green-200/40 text-foreground" : "bg-muted text-muted-foreground"}`}
              >
                {document.status ? labels[document.status] : ""}
              </span>
              <Popover>
                <PopoverTrigger
                  render={
                    <Button
                      aria-label={`Ações para ${document.name}`}
                      size="icon-sm"
                      variant="ghost"
                    >
                      <Ellipsis />
                    </Button>
                  }
                />
                <PopoverContent>
                  <PopoverClose
                    render={
                      <Button variant="ghost" onClick={() => onOpen(document)}>
                        Abrir
                      </Button>
                    }
                  />
                  <PopoverClose
                    render={
                      <Button
                        variant="ghost"
                        onClick={() => onRename(document)}
                      >
                        <Pencil />
                        Renomear
                      </Button>
                    }
                  />
                  <PopoverClose
                    render={
                      <Button
                        variant="ghost"
                        onClick={() => onDelete(document)}
                      >
                        <Trash2 />
                        Excluir
                      </Button>
                    }
                  />
                </PopoverContent>
              </Popover>
            </>
          )}
        </div>
      </CardHeader>
    </Card>
  );
}
