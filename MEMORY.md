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
- 2026-11-27: the running workspace server was registered as a Hermes MCP server (`hermes mcp add receipty --url http://127.0.0.1:9000/mcp/`). `hermes mcp test receipty` connects in ~310 ms and discovers 15 tools (prefixed `mcp_receipty_*`). MCP tools load at session start; start a new session or run `/reload-mcp` to enable them. This replaces the REST-only fallback in the installed receipty skill.

## Receipt field conventions

- Use `tags` (a JSON list of lowercase English strings) instead of `category`. A receipt can have multiple tags. This is a field convention within the existing arbitrary JSON model, not a dedicated database column or tag picker.
- Receipts require a non-empty string `title` and `date`; `date` may be the
  literal `"todo"` when unknown. `description` is optional. The list view shows
  `title` and `date`; the browser editor exposes all three separately (description
  as a multi-line field) and keeps tags in Additional fields (JSON). Description
  is removed when it is identical to the title. Receipt search matches tags as
  part of the JSON fields. Legacy receipts missing `title` or `date` are backfilled
  on startup (title from description or first attachment name, date to `"todo"`).
- The quick-create form on the list view shows only `title` and `date` (no
  description). It sits next to the search form on the same toolbar line: both
  forms are flex:1 1 0 so the line fills the available width, both main inputs
  (`query` and `title`) flex to equal width, the state select is fixed at 7rem
  (border-box), the date picker is ~8.5rem, and the Search/Create buttons are
  fixed at 5.5rem.
  The toolbar gap is 1.5rem. The detail editor still exposes `description`.
  When the fields would drop below 250px wide (toolbar container < 962px, a
  `@container` rule with a `@media (max-width: 1070px)` fallback), both forms
  stack full-width on separate lines (mobile-first).
- Both date fields (quick-create and the detail editor) use a native
  `<input type="date">` picker (YYYY-MM-DD) plus a "todo" checkbox. The picker
  is unnamed; a hidden `name="date"` input carries the submitted value —
  `"todo"` when the checkbox is checked, otherwise the picker's date. The
  shared `static/date-picker.js` (loaded by `base.html`) greys the picker
  when "todo" is checked and syncs the hidden field on change. Hidden value
  empty + unchecked => server 400 (unchanged). The list-view CSS gives the
  picker ~8.5rem.
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
- On 2026-11-19, the skill was copied to this machine's `~/.hermes/skills/productivity/receipty/` and byte-verified. On 2026-11-27 it was re-copied and byte-verified after adding the title-required/description-optional field rules; the same session then patched the installed copy in place (title+date required, date in list view) via skill_manage rather than a byte-verified copy. On 2026-11-27 the installed copy was verified byte-identical to the repo (diff and shasum). The installed files are a separate copy; future repo edits need to be copied to Hermes again.
- Skill structure validation passed with the skill-creator `quick_validate.py` script. Discovery was verified; an end-to-end Hermes receipt workflow was not run.

## Verification

- 2026-11-19: denied-access guidance, permission request error rendering, and receipt preservation verified; existing receipt, workspace, and managed Photos import tests passed.
- 2026-11-27: `pytest -q` passed all 12 tests. Coverage includes mandatory title/date enforcement (create, patch, merge), legacy title/date backfill, duplicate description removal, and UI create/list/detail date rendering, plus the existing receipt, workspace, and managed Photos import tests.
- 2026-11-27: the list-view quick-create form was changed to title+date only (description removed) and laid out on one toolbar line (search form left, title filling the remaining space, fixed 7rem date, 1.5rem toolbar gap). Layout was verified live in a browser (element rects and date-overflow check with a sample date) on a scratch workspace; the 12 tests were re-run after the CSS changes.
- 2026-11-27: search and title fields in the list-view toolbar were made equal width (both forms flex:1 1 0, both inputs flex:1 1 auto, state select and date fixed at 7rem, Search/Create buttons fixed at 5.5rem, toolbar gap 1.5rem). `pytest -q` passed all 12 tests after the CSS changes.
- 2026-11-27: the list-view toolbar became a CSS container and both forms stack full-width on separate lines when the search/title inputs would drop below 250px (`@container (max-width: 962px)` with a `@media (max-width: 1070px)` fallback). Verified live in a browser at 1280px (side by side, 268.8px inputs) and 375px (stacked) plus 756px (stacked); `pytest -q` passed all 12 tests.
- 2026-11-27: the quick-create and detail date fields were changed from free-text inputs to native date pickers (YYYY-MM-DD) with a "todo" checkbox. `pytest -q` passed all 12 tests; pages were rendered over HTTP and the picker, hidden input, checkbox, and shared JS were verified in the markup and the JS served 200. Browser popup behavior not visually verified.
- 2026-11-27: the receipt list gained sorting by date and title (UI "Sort by" bar, REST `sort`/`direction` query params; date sort pins "todo" dates last). `pytest -q` passed all 13 tests; the UI was verified live in a browser (sort links, active state, toggle). Note: a running server keeps its loaded Python code — restart it after code changes or the UI can render new templates against stale routes (e.g. empty sort-bar links).
