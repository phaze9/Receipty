#!/usr/bin/env python3
# OCR for multiple images passed via command-line

import os, sys
from PIL import Image
import pytesseract

# Define the OCR function
def ocr_image(file_path):
    try:
        image = Image.open(file_path)
        # Specify languages English and Thai for Tesseract
        return file_path, pytesseract.image_to_string(image, lang='eng+tha')
    except IOError:
        # Return None if the file is not an image or cannot be opened
        return None, None

# Collect any files including in folders and subfolders
def get_files_to_process(args):
    for arg in args:
        if os.path.isfile(arg) and arg.endswith(('.jpg', '.jpeg', '.png', '.bmp')):
            yield arg
        elif os.path.isdir(arg):
            for root, _, files in os.walk(arg):
                for file in files:
                    if file.endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                        yield os.path.join(root, file)

# Get the list of file paths from the command-line arguments
if len(sys.argv) < 2:
    print("Error: Please provide at least one file or folder as an argument.")
    sys.exit(1)

# Apply OCR to each image and print results immediately
for fp in get_files_to_process(sys.argv[1:]):
    result = ocr_image(fp)
    if result is not None:
        print(f"File: {result[0]}")
        print(result[1])
        print("-" * 80)
