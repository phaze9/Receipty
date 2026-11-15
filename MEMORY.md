# Repo memory

Durable facts about the Receipty project. Keep this to facts only.

## Project

- Receipty OCRs receipts and saves the extracted text. Previously named "Receipts" — renamed repo, folder, and IntelliJ module to "Receipty" on 2026-11-11:
  - GitHub repo: `phaze9/Receipty` (was `phaze9/Receipts`; remote redirected, so old URLs still work).
  - Folder: `~/Projects/Receipty` (was `~/Projects/Receipts`).
  - IntelliJ module: `Receipty.iml` at repo root, tracked. Uses the relative `$MODULE_DIR$` path, so the module reference is the filename itself — no `.idea/` project cache is tracked.
  - README title is `# Receipty`.

## Pipeline

Three cooperating scripts, wired by shell piping rather than a package:

- `grab_text.py` — OCR. Takes one or more files/folders as CLI args; walks subfolders; only processes `.jpg/.jpeg/.png/.bmp`. Uses `pytesseract.image_to_string` with `lang='eng+tha'` (English + Thai, since these are receipts). Prints for each file a `File: <path>` line, the OCR text, then a separator of 80 dashes, streaming results per file. Exits 1 with a usage message if no args.
- `main.py` — driver. Runs `python3 grab_text.py <args…>` via `subprocess.run` (capture stdout, `check=True`), parses the output against the same `File: ` / 80-dash separator protocol, and writes each file's OCR text to `<original path>.text` (same base name, `.text` extension) via `save_ocr_text`. The protocol (prefix `File: ` and separator `-` × 80) is shared between the two scripts by convention — change one, change the other.
- `translate_to_english.py` — translation, not called from `main.py`; a standalone pipe target. Reads text from stdin, sends it to Ollama (`http://localhost:11434/v1/`) through the OpenAI Python SDK, model `llama3.1-8b-q8` (comment notes the model string can be any loaded local model), temperature 0.9, prints the translation to stdout; empty stdin exits silently.

## Environment

- No dependency manifest (`requirements.txt`/`pyproject.toml`) is tracked. Imports: `PIL` (Pillow), `pytesseract`, `openai`. Plus system deps: Tesseract OCR installed with `eng` and `tha` language data, and Ollama running on port 11434 for the translate script.
- `.worktrees/` is gitignored (holds linked git worktrees, e.g. `hermes-f37c8d92`).
