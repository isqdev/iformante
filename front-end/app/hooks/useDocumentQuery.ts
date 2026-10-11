"use client";
import { useCallback, useEffect, useState } from "react";
export function useDocumentQuery() {
  const [id, setId] = useState<string | null>(null);
  useEffect(() => {
    const read = () =>
      setId(new URL(window.location.href).searchParams.get("document"));
    queueMicrotask(read);
    window.addEventListener("popstate", read);
    return () => window.removeEventListener("popstate", read);
  }, []);
  const select = useCallback((value: string | null) => {
    const url = new URL(window.location.href);
    if (value) url.searchParams.set("document", value);
    else url.searchParams.delete("document");
    window.history.pushState(null, "", url);
    setId(value);
  }, []);
  return [id, select] as const;
}
