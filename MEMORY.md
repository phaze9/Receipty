# Repo memory

Durable facts about the Receipty project. Keep this to facts only.

## Project

- Receipty OCRs receipts and saves the extracted text. Previously named "Receipts" — renamed repo, folder, and IntelliJ module to "Receipty" on 2026-11-11:
  - GitHub repo: `phaze9/Receipty` (was `phaze9/Receipts`; remote redirected, so old URLs still work).
  - Folder: `~/Projects/Receipty` (was `~/Projects/Receipts`).
  - IntelliJ module: `Receipty.iml` at repo root, tracked. Uses the relative `$MODULE_DIR$` path, so the module reference is the filename itself — no `.idea/` project cache is tracked.
  - README title is `# Receipty`.

## Legacy scripts

The original scripts remain available alongside the workspace server:

- `grab_text.py` — OCR. Takes one or more files/folders as CLI args; walks subfolders; only processes `.jpg/.jpeg/.png/.bmp`. Uses `pytesseract.image_to_string` with `lang='eng+tha'` (English + Thai, since these are receipts). Prints for each file a `File: <path>` line, the OCR text, then a separator of 80 dashes, streaming results per file. Exits 1 with a usage message if no args.
- `main.py` — driver. Runs `python3 grab_text.py <args…>` via `subprocess.run` (capture stdout, `check=True`), parses the output against the same `File: ` / 80-dash separator protocol, and writes each file's OCR text to `<original path>.text` (same base name, `.text` extension) via `save_ocr_text`. The protocol (prefix `File: ` and separator `-` × 80) is shared between the two scripts by convention — change one, change the other.
- `translate_to_english.py` — translation, not called from `main.py`; a standalone pipe target. Reads text from stdin, sends it to Ollama (`http://localhost:11434/v1/`) through the OpenAI Python SDK, model `llama3.1-8b-q8` (comment notes the model string can be any loaded local model), temperature 0.9, prints the translation to stdout; empty stdin exits silently.

## Environment

- `pyproject.toml` declares the workspace server dependencies and the `receipty` CLI; Python 3.12 or newer is required. Image OCR needs Tesseract with `eng` and `tha` language data. The legacy translation script additionally needs the OpenAI Python SDK and its configured Ollama model.
- `.worktrees/` is gitignored (holds linked git worktrees, e.g. `hermes-f37c8d92`).

## Workspace server

- `src/receipty/` contains the FastAPI browser UI, REST API, Streamable HTTP MCP server, SQLite models, recursive watcher, and extraction worker. Start with `receipty serve /path/to/workspace`; the default UI is `http://127.0.0.1:9000/`, REST documentation is `/docs`, and MCP is `/mcp/`.
- The workspace reserves `receipt-files/` for source files and `.receipty/` for its database, configuration, and caches. Other top-level workspace entries are left alone. Supported new files create draft receipts; receipt fields support arbitrary JSON.
- `receipty.sh` launches the server using an available virtual environment and forwards the workspace and CLI options. It currently assumes the project lives at `$HOME/Projects/Receipty`.
- The launcher requires a workspace argument, accepts options such as `--port`, and selects Python from project `.venv`, project `venv`, `$HOME/venv`, then `python3`. It sets `PYTHONPATH` to the checkout's `src/` directory. Its shell syntax and CLI help were checked. Placement in `$HOME/Projects/Agent` was blocked by filesystem policy; the launcher is available at the repository root.

## Receipt field conventions

- Use `tags` (a JSON list of lowercase English strings) instead of `category`. A receipt can have multiple tags. This is a field convention within the existing arbitrary JSON model, not a dedicated database column or tag picker.
- Receipts require a non-empty string `title`; `description` is optional. The list view shows `title`; the browser editor exposes both separately (description as a multi-line field) and keeps tags in Additional fields (JSON). Description is removed when it is identical to the title. Receipt search matches tags as part of the JSON fields.
- REST and MCP field updates replace the entire fields object. Fetch the current receipt, merge requested changes, and preserve unrelated fields before submitting an update.
- Keep project documentation general: omit workspace-specific paths, receipt contents, identifiers, and inventories.

## Implementation limits

- The initial implementation is partial relative to the original v1 plan. Search currently uses SQL `LIKE`, not FTS5. Database initialization uses SQLAlchemy `create_all`; Alembic is declared but no migrations are implemented. There is no `uv.lock`.
- Current watcher rename reconciliation uses filesystem identity, not a hash fallback. Existing file modifications do not automatically enqueue fresh extraction. Managed Photos imports currently export directly to their destination; atomic import and watcher deduplication coordination remain to be implemented.
- PDF and DOCX extraction require the `documents` extra; missing optional libraries are reported through extraction method metadata. Image/PDF OCR needs the external Tesseract installation and language packs.

## Apple Photos

- The native PhotoKit helper lives in `macos/ReceiptyPhotosHelper/`. Build its ad-hoc signed app using `sh macos/ReceiptyPhotosHelper/build-helper.sh`. `RECEIPTY_PHOTOS_HELPER` overrides the helper executable path.
- Individual assets support managed copies under `receipt-files/<year>/` with PhotoKit provenance or references. Albums support dynamic links and snapshots of asset IDs. PhotoKit identifiers are device-local.
- On 2026-11-19, the installed helper's live `authorization` response was `denied`. Repeated permission requests retain that status; the UI now explains how to enable access in System Settings → Privacy & Security → Photos and provides a settings link and refresh link. Restricted access has separate guidance.
- Authorization request failures render on the Photos page. Helper startup failures and timeouts become `PhotosUnavailable` errors. Successful request redirects preserve the target receipt.
- Access must still be enabled in macOS settings by the user. Authorized library browsing and imports were not verified during this fix.

## Receipty agent skill

- Always return a clickable receipt detail link when creating a new receipt, including through imports or watcher discovery. Use the connected server's base URL plus `/receipts/<receipt_id>`; include a link for each new receipt even when extraction is pending.
- `skills/receipty/SKILL.md` is the repo-maintained skill for searching, importing, organizing, and correcting receipts through Receipty MCP tools or the REST API. `skills/receipty/references/api.md` documents REST endpoints and request shapes.
- The skill covers workspace verification, full-replacement field updates, watcher-created drafts, merge behavior, background extraction, and Apple Photos authorization and attachment modes.
- On 2026-11-19, the skill was copied to this machine's `~/.hermes/skills/productivity/receipty/` and byte-verified. On 2026-11-27 it was re-copied and byte-verified after adding the title-required/description-optional field rules. The installed files are a separate copy; future repo edits need to be copied to Hermes again.
- Skill structure validation passed with the skill-creator `quick_validate.py` script. Discovery was verified; an end-to-end Hermes receipt workflow was not run.

## Verification

- 2026-11-19: denied-access guidance, permission request error rendering, and receipt preservation verified; existing receipt, workspace, and managed Photos import tests passed.
- 2026-11-27: `pytest -q` passed all 11 tests. Coverage includes mandatory title enforcement and backfill, duplicate description removal, and the existing receipt, workspace, and managed Photos import tests.
