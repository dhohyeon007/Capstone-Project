from google import genai
from google.genai import types
import time
import os
import io
import sys

os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

client = genai.Client(api_key="API KEY")

chat = client.chats.create(
    model="gemini-2.5-flash",
    config=types.GenerateContentConfig(
        temperature=0.7
    )
)

print("[ Gemini Response Bot ]")
print("*" * 50)

while True:
    user_input = input("User: ")

    if user_input.lower() == "q":
        print("Exiting the chat. Goodbye!")
        sys.exit(0)

    if not user_input.strip():
        print("Please enter a valid message.")
        continue

    try:
        response = chat.send_message(user_input)
        with open("gemini_responses.md", "w", encoding="utf-8") as file:
            file.write(response.text)

        print(f"Gemini: {response.text}")

    except Exception as e:
        if "503" in str(e):
            print("waiting...")
            time.sleep(5)
            continue

        else:
            print(f"An error occurred: {e}")