"use client";

import {
  Children,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";
import {Table} from "@heroui/react";
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
  const headerCells = extractTableRows(tableHead, "th")[0] ?? [];
  const bodyRows = extractTableRows(tableBody, "td");
  const columnCount = Math.max(
    headerCells.length,
    ...bodyRows.map((row) => row.length),
    0,
  );

  if (columnCount === 0) {
    return (
      <div className="my-4 overflow-x-auto">
        <table className="w-full text-left text-sm">{children}</table>
      </div>
    );
  }

  const columns = Array.from({length: columnCount}, (_, index) => {
    return headerCells[index] ?? `Coluna ${index + 1}`;
  });
  const rows = bodyRows.map((row) =>
    Array.from({length: columnCount}, (_, index) => row[index] ?? ""),
  );

  return (
    <Table className="my-4">
      <Table.ScrollContainer>
        <Table.Content aria-label="Tabela da resposta">
          <Table.Header>
            {columns.map((column, index) => (
              <Table.Column key={`column-${index}`}>{column}</Table.Column>
            ))}
          </Table.Header>
          <Table.Body>
            {rows.map((row, rowIndex) => (
              <Table.Row key={`row-${rowIndex}`}>
                {row.map((cell, cellIndex) => (
                  <Table.Cell key={`cell-${rowIndex}-${cellIndex}`}>
                    {cell}
                  </Table.Cell>
                ))}
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Content>
      </Table.ScrollContainer>
    </Table>
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
          <code className="rounded bg-default-100 px-1.5 py-0.5 text-[0.85em]">
            {children}
          </code>
        ),
        li: ({children}) => <li className="pl-1">{children}</li>,
        ol: ({children}) => (
          <ol className="my-3 list-decimal space-y-1 pl-5">{children}</ol>
        ),
        p: ({children}) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
        pre: ({children}) => (
          <pre className="my-3 overflow-x-auto rounded-lg bg-default-100 p-3 text-xs leading-6">
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
