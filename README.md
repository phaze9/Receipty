# Receipty

Receipty is a local-first receipt workspace with a browser UI, REST API, and
Model Context Protocol server. Receipt fields are arbitrary JSON, while source
files remain ordinary files inside the workspace.

## Receipt fields

Receipts have a required, non-empty `title` and `date` (use `"todo"` when the
date is unknown), and an optional `description`; the
list view shows `title` and `date`. If `description` is identical to `title`, it
is removed. Legacy receipts missing a title or date are backfilled on startup
(title from description or first attachment name, date to `"todo"`). Organize
receipts with `tags`, a list of lowercase English strings,
instead of a `category` field. A receipt can have multiple tags:

```json
{"title": "Example receipt", "date": "2026-11-27", "tags": ["food", "travel"]}
```

The browser editor exposes title, date and description separately (description as a
multi-line field); enter tags in Additional fields as JSON. Receipt search
matches tags along with other fields and extracted text. Through REST or MCP,
submitting `fields` replaces the entire fields object, so fetch the receipt
first and preserve unrelated fields.

## Development

Receipty requires Python 3.12 and Tesseract with the English and Thai language
packs for image OCR.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,documents]'
.venv/bin/receipty serve /path/to/workspace
```

Open <http://127.0.0.1:9000/> for the UI, `/docs` for the REST API, or connect
an MCP client to `http://127.0.0.1:9000/mcp/` using Streamable HTTP.

The server creates only these reserved paths in a workspace:

```text
receipt-files/       recursively watched receipt files
.receipty/           SQLite database, configuration, and generated caches
```

Other top-level files and folders are left alone. New supported files below
`receipt-files/`, including yearly subfolders, create draft receipts and are
processed by the background extraction worker.

## Apple Photos

Build the signed local helper after installing a matching Xcode/Command Line
Tools toolchain:

```bash
sh macos/ReceiptyPhotosHelper/build-helper.sh
```

On first use, macOS asks for Photos access. Individual assets default to a
managed copy under `receipt-files/<year>/` while retaining their PhotoKit ID as
provenance. Albums can be linked dynamically or as a snapshot of asset IDs.

Set `RECEIPTY_PHOTOS_HELPER` to the bundled helper executable if it is installed
outside the repository.

## Tests

```bash
PYTHONPATH=src pytest
```
