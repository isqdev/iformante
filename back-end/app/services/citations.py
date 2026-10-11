def group_citations(items):
    """One source per document, every used chunk retained in retrieval order."""
    grouped = {}
    for item in items:
        document = grouped.setdefault(item["document_id"], {key: item[key] for key in ("document_id", "filename", "url", "source_type")})
        citations = document.setdefault("citations", [])
        if item["chunk_id"] and not any(c["chunk_id"] == item["chunk_id"] for c in citations):
            citations.append({"chunk_id": item["chunk_id"], "anchors": item.get("bbox") or []})
    return list(grouped.values())
