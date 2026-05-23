import os
import sys
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception
from google import genai
from google.genai import types


client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))


def select_file():
    current_dir = os.getcwd()

    while True:
        items = [
            entry.name for entry in os.scandir(current_dir)
            if entry.name.endswith(".pdf") or entry.is_dir()
        ]
        print(f"Current Directory: {current_dir}")
        print("0. .. (Go to parent directory)")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item}")

        choice = input("Select a file or directory (enter number): ")
        if choice == "-1":
            sys.exit(0)
        elif choice == "0":
            current_dir = os.path.dirname(current_dir)
        else:
            try:
                index = int(choice) - 1
                selected_item = items[index]
                target_path = os.path.join(current_dir, selected_item)
                if os.path.isdir(selected_item):
                    current_dir = target_path
                else:
                    return target_path
            except (ValueError, IndexError):
                print("Invalid choice. Please try again.")


def is_retryable_error(exception):
    error_str = str(exception).lower()
    return any(keyword in error_str for keyword in ["429", "503"])


@retry(
        wait=wait_random_exponential(multiplier=1, max=60),
        stop=stop_after_attempt(),
        retry=retry_if_exception(is_retryable_error)
)
def call_gemini_api(contents, schema):
    return client.models.generate_content(
        model='gemini-3-pro-preview',
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0
        )
    )