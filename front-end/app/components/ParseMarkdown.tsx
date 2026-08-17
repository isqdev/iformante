"use client";

import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import type {ColumnDef} from "@tanstack/react-table";
import {DataTable} from "@/components/ui/data-table";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type ParseMarkdownProps = {
  content: string;
};

type ElementWithChildren = ReactElement<{children?: ReactNode}>;

function getElementType(node: ReactNode) {
  return isValidElement(node) && typeof node.type === "string"
    ? node.type
    : null;
}

function getElementChildren(node: ReactNode) {
  return isValidElement(node)
    ? (node as ElementWithChildren).props.children
    : null;
}

function extractTableRows(section: ReactNode, cellType: "td" | "th") {
  const sectionChildren = Children.toArray(getElementChildren(section));

  return sectionChildren
    .filter((child) => getElementType(child) === "tr")
    .map((row) =>
      Children.toArray(getElementChildren(row))
        .filter((cell) => getElementType(cell) === cellType)
        .map((cell) => getElementChildren(cell)),
    )
    .filter((row) => row.length > 0);
}

function MarkdownTable({children}: {children: ReactNode}) {
  const tableSections = Children.toArray(children);
  const tableHead = tableSections.find((child) => getElementType(child) === "thead");
  const tableBody = tableSections.find((child) => getElementType(child) === "tbody");
  const explicitHeaderCells = extractTableRows(tableHead, "th")[0] ?? [];
  const extractedBodyRows = extractTableRows(tableBody, "td");
  const headerCells =
    explicitHeaderCells.length > 0
      ? explicitHeaderCells
      : (extractedBodyRows[0] ?? []);
  const bodyRows =
    explicitHeaderCells.length > 0
      ? extractedBodyRows
      : extractedBodyRows.slice(1);
  const columnCount = Math.max(
    headerCells.length,
    ...bodyRows.map((row) => row.length),
    0,
  );

  const rows = bodyRows.map((row) =>
    Array.from({length: columnCount}, (_, index) => row[index] ?? ""),
  );
  const columns: ColumnDef<ReactNode[]>[] = Array.from(
    {length: columnCount},
    (_, index) => ({
      id: `column-${index}`,
      header: () => headerCells[index] ?? `Coluna ${index + 1}`,
      cell: ({row}) => row.original[index] ?? "",
    }),
  );

  return (
    <div className="my-4">
      <DataTable
        ariaLabel="Tabela da resposta"
        columns={columns}
        data={rows}
      />
    </div>
  );
}

export function ParseMarkdown({content}: ParseMarkdownProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a: ({children, href}) => (
          <a
            className="font-medium underline underline-offset-4"
            href={href}
            rel="noreferrer"
            target="_blank"
          >
            {children}
          </a>
        ),
        code: ({children}) => (
          <code className="rounded bg-muted px-1.5 py-0.5 text-[0.85em]">
            {children}
          </code>
        ),
        h1: ({children}) => (
          <h1 className="mb-3 mt-6 text-2xl font-bold leading-tight first:mt-0">
            {children}
          </h1>
        ),
        h2: ({children}) => (
          <h2 className="mb-2.5 mt-5 text-xl font-bold leading-tight first:mt-0">
            {children}
          </h2>
        ),
        h3: ({children}) => (
          <h3 className="mb-2 mt-4 text-lg font-semibold leading-snug first:mt-0">
            {children}
          </h3>
        ),
        h4: ({children}) => (
          <h4 className="mb-2 mt-4 text-base font-semibold leading-snug first:mt-0">
            {children}
          </h4>
        ),
        h5: ({children}) => (
          <h5 className="mb-1.5 mt-3 text-sm font-semibold leading-normal first:mt-0">
            {children}
          </h5>
        ),
        h6: ({children}) => (
          <h6 className="mb-1.5 mt-3 text-xs font-semibold uppercase leading-normal tracking-wide first:mt-0">
            {children}
          </h6>
        ),
        li: ({children}) => <li className="pl-1">{children}</li>,
        ol: ({children}) => (
          <ol className="my-3 list-decimal space-y-1 pl-5">{children}</ol>
        ),
        p: ({children}) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
        pre: ({children}) => (
          <pre className="my-3 overflow-x-auto rounded-lg bg-muted p-3 text-xs leading-6">
            {children}
          </pre>
        ),
        strong: ({children}) => <strong className="font-semibold">{children}</strong>,
        table: ({children}) => <MarkdownTable>{children}</MarkdownTable>,
        ul: ({children}) => (
          <ul className="my-3 list-disc space-y-1 pl-5">{children}</ul>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
