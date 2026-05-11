from google import genai
from google.genai import types
import time

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
        break

    if not user_input.strip():
        print("Please enter a valid message.")
        continue

    try:
        response = chat.send_message(user_input)
        print(f"Gemini: {response.text}")

    except Exception as e:
        if "503" in str(e):
            print("waiting...")
            time.sleep(5)
            continue
        else:
            print(f"An error occurred: {e}")
