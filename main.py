#!/usr/bin/env python3

import subprocess
import os
import sys

# Saves the OCR'd text to a file with a .text extension.
# Assumes original_filepath is the full path to the original image.
def save_ocr_text(original_filepath, text_content):
    base, _ = os.path.splitext(original_filepath)
    text_filename = base + ".text"

    with open(text_filename, "w", encoding="utf-8") as f:
        f.write(text_content)

def save_current_file():
    if current_file and current_text_buffer:
        save_ocr_text(current_file, "\n".join(current_text_buffer))

# Assuming grab_text.py is in the same directory or accessible in PATH
command = ["python3", "grab_text.py"] + sys.argv[1:]

# Execute grab_text.py and capture its output, text=True decodes stdout/stderr as text
result = subprocess.run(command, capture_output=True, text=True, check=True)

# Process the captured output
output_lines = result.stdout.splitlines()
current_file = None
current_text_buffer = []

for line in output_lines:
    if line.startswith("File: "):
        # New file detected, save previous text if any
        save_current_file()
        current_file = line.replace("File: ", "").strip()
        current_text_buffer = []
    elif line.startswith("-" * 80):
        # End of a file's OCR output
        save_current_file()
        current_text_buffer = []
        current_file = None
    elif current_file:
        current_text_buffer.append(line)

# Save any remaining text for the last file
if current_file and current_text_buffer:
    save_ocr_text(current_file, "\n".join(current_text_buffer))
