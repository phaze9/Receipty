# REST fallback

Use the verified server base URL; paths below are relative to `/api/v1`.
Send JSON bodies with `Content-Type: application/json`. Check HTTP errors before
interpreting a response as a result. The server accepts loopback connections.

| Operation | Method and path | Parameters or JSON body |
| --- | --- | --- |
| Workspace | `GET /workspace` | Returns root and receipt-files paths |
| Discover files | `POST /workspace/rescan` | No body |
| Search/list | `GET /receipts` | Query: `query`, `state`, `field_key`, `field_value`, `offset`, `limit` (1–200) |
| Get receipt | `GET /receipts/{id}` | Includes fields and attachment extraction results |
| Create | `POST /receipts` | `{"fields": {...}, "state": "draft"}` |
| Update | `PATCH /receipts/{id}` | Optional `fields` (full replacement), `state` (`draft`, `active`, `archived`, `deleted`) |
| Archive/restore | `POST /receipts/{id}/archive` or `/restore` | No body; restore sets draft |
| Purge | `POST /receipts/{id}/purge` | No body; only deleted receipts past the 30-day retention window; deletes DB records, leaves files on disk |
| Merge | `POST /receipts/merge` | `{"source_ids": ["..."], "target_id": "..."}` |
| Attach file | `POST /receipts/{id}/attachments` | `{"path": "receipt-files/2026/example.pdf"}` |
| Source file | `GET /attachments/{id}/content` | Binary response |
| Retry extraction | `POST /attachments/{id}/retry` | Returns 202 queued |
| Detach | `DELETE /attachments/{id}` | Deletes attachment record and jobs, leaves source file |
| Photos access | `GET /photos/authorization` | Current authorization response |
| Request access | `POST /photos/authorization` | Requests macOS authorization |
| Albums | `GET /photos/albums` | No body |
| Assets | `GET /photos/assets` | Optional `album_id` query |
| Link asset | `POST /receipts/{id}/photos/assets` | `{"asset_id": "...", "mode": "managed_copy"}` or reference |
| Link album | `POST /receipts/{id}/photos/albums` | `{"album_id": "...", "mode": "dynamic"}` or snapshot |

REST exposes one field filter per request; MCP accepts a `field_filters` object.
Query results are ordered by most recently updated receipt. Detaching a file in
the watched tree can allow a later scan to register it as a new draft; detachment
is not an exclusion mechanism. Deleted receipts are excluded from list/search
unless the `deleted` state is requested explicitly.

`title` and `date` are required on create and on field updates (requests without
them return 400). `date` is a free-form string; use `"todo"` when the date is
unknown. `description` is optional; a description identical to the title is
removed rather than stored twice.

Read-only examples (replace the base URL when using another port):

```sh
curl --fail-with-body --silent --show-error http://127.0.0.1:9000/api/v1/workspace
curl --fail-with-body --silent --show-error --get \
  --data-urlencode 'query=coffee' --data-urlencode 'state=active' \
  --data-urlencode 'limit=50' --data-urlencode 'offset=0' \
  http://127.0.0.1:9000/api/v1/receipts
```

For writes, serialize the JSON with a JSON library into a temporary file and
pass it using `curl --data-binary @/path/to/body.json`. Avoid interpolating OCR
text into shell code. Fetch the receipt again after a successful write.
