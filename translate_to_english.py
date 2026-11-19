#!/usr/bin/env python3

import sys
from openai import OpenAI

def translate_to_english_from_stdin():
    # Initialize the OpenAI client to connect to your local Ollama endpoint
    client = OpenAI(
        base_url="http://localhost:11434/v1/",
        api_key="ollama", # Required, but can be any value
    )

    # Read all lines from stdin
    text_lines = sys.stdin.readlines()
    text = "".join(text_lines).strip()

    if not text:
        # Exit silently if no input, as it's intended for shell piping
        return

    full_prompt = f"Please translate this to English, return translated text only: {text}"

    try:
        # Create a chat completion request
        chat_completion = client.chat.completions.create(
            model="llama3.1-8b-q8", # This can be any string, as it's a local model
            messages=[
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.9, # You can adjust this value
        )

        # Extract the translated content
        if chat_completion.choices and chat_completion.choices[0].message:
            translated_text = chat_completion.choices[0].message.content
            sys.stdout.write(translated_text.strip() + "\n")
        else:
            sys.stderr.write("Translation failed: No content in the response.\n")

    except Exception as e:
        sys.stderr.write(f"An error occurred during translation: {e}\n")

if __name__ == "__main__":
    translate_to_english_from_stdin()
