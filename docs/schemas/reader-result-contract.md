# Reader Result Contract

Every reader should return the same shape so the hub can compare them.

```json
{
  "reader_id": "pdf-extractor",
  "path": "D:/example/file.pdf",
  "status": "ok",
  "content_type": "application/pdf",
  "text": "optional extracted text",
  "text_hash": "optional",
  "metadata": {
    "page_count": 12,
    "title": "Optional title"
  },
  "confidence": 0.9,
  "errors": []
}
```

If the reader fails:

```json
{
  "reader_id": "pdf-extractor",
  "path": "D:/example/file.pdf",
  "status": "failed",
  "content_type": "application/pdf",
  "text": "",
  "metadata": {},
  "confidence": 0.0,
  "errors": ["pypdf not installed"]
}
```

The hub should not lose failures. Failed reads become useful reader-backlog data.

