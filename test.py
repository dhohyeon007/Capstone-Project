from google import genai
from google.genai import types
import time
import os

client = genai.Client(api_key="API KEY")

print("[ Gemini Response Bot ]")
print("*" * 50)

while True:
    user_input = input("Upload: ")

    if user_input.lower() == "q":
        print("Exiting the chat. Goodbye!")
        break

    if not user_input.strip() or not os.path.isfile(user_input):
        print("Please enter a valid file path.")
        continue

    try:
        file = client.files.upload(file=user_input)
        abs_path = os.path.abspath(user_input)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=["파일 요약해줘.", abs_path],
        )
        
        with open("response.txt", "w") as f:
            f.write(response.text)

    except Exception as e:
        if "503" in str(e):
            print("waiting...")
            time.sleep(5)
            continue
        else:
            print(f"An error occurred: {e}")