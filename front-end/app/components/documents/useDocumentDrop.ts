"use client";
import { useEffect, useState } from "react";
export type DroppedSource = { file?: File; url?: string; title?: string };
export function ifprUrl(value: string) {
  try {
    const u = new URL(value);
    return ["http:", "https:"].includes(u.protocol) &&
      !u.username &&
      !u.password &&
      (u.hostname === "ifpr.edu.br" || u.hostname.endsWith(".ifpr.edu.br"))
      ? u.href
      : null;
  } catch {
    return null;
  }
}
export function useDocumentDrop(
  admin: boolean,
  onDrop: (source: DroppedSource) => void,
) {
  const [recognized, setRecognized] = useState(false);
  useEffect(() => {
    if (!admin) return;
    let depth = 0;
    function inspect(data: DataTransfer) {
      const file =
        data.files.item(0) ??
        Array.from(data.items)
          .find((i) => i.kind === "file")
          ?.getAsFile();
      const text =
        data
          .getData("text/uri-list")
          .split("\n")
          .find((line) => line && !line.startsWith("#")) ??
        data.getData("text/plain");
      return file?.name.toLowerCase().endsWith(".pdf")
        ? { file, title: file.name.replace(/\.pdf$/i, "") }
        : ifprUrl(text)
          ? { url: ifprUrl(text)! }
          : null;
    }
    function enter(event: DragEvent) {
      depth++;
      if (event.dataTransfer && inspect(event.dataTransfer))
        setRecognized(true);
    }
    function over(event: DragEvent) {
      if (!event.dataTransfer) return;
      if (
        event.dataTransfer.types.some((t) =>
          ["Files", "text/uri-list", "text/plain"].includes(t),
        )
      )
        event.preventDefault();
      if (inspect(event.dataTransfer)) {
        event.dataTransfer.dropEffect = "copy";
        setRecognized(true);
      }
    }
    function leave() {
      depth--;
      if (depth <= 0) {
        depth = 0;
        setRecognized(false);
      }
    }
    function drop(event: DragEvent) {
      depth = 0;
      setRecognized(false);
      if (!event.dataTransfer) return;
      const source = inspect(event.dataTransfer);
      if (source) {
        event.preventDefault();
        onDrop(source);
      } else if (event.dataTransfer.types.includes("Files"))
        event.preventDefault();
    }
    function end() {
      depth = 0;
      setRecognized(false);
    }
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    window.addEventListener("dragend", end);
    return () => {
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
      window.removeEventListener("dragend", end);
    };
  }, [admin, onDrop]);
  return recognized;
}
