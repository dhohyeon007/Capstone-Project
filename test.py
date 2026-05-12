from google import genai
from google.genai import types
import time
import os
import sys
import io

save_path = os.getcwd() + "/README.md"

os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))

print("[ Gemini Response Bot ]")
print("*" * 50)

while True:
    current_dir = os.getcwd()
    print(f"Current Directory: {current_dir}")

    items = os.listdir(current_dir)
    print("0. .. (Go to parent directory)")
    for i, item in enumerate(items, 1):
        print(f"{i}. {item}")

    try:
        choice = int(input("Select a file or directory (enter the number): "))

        if choice == -1:
            break
        elif choice == 0:
            os.chdir("..")
            continue

        selected_name = items[choice - 1]
        full_path = os.path.abspath(selected_name)

        if os.path.isdir(full_path):
            os.chdir(full_path)
        
        else:
            try:
                file = client.files.upload(file=full_path)
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=["캡스톤 프로젝트 주제 공고 pdf를 보고 예상 프로젝트 결과물에 대한 README.md 파일을 작성해줘.", file],
                )
                
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(response.text)

            except Exception as e:
                if "503" in str(e):
                    print("waiting...")
                    time.sleep(5)
                    continue
                else:
                    print(f"An error occurred: {e}")
                
    except (ValueError, IndexError):
        print("Invalid input. Please enter a valid number.")
