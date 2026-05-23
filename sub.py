# from google import genai
import os
import sys
import fitz
import pandas as pd
import json


# client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))


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


def refine_table_for_llm(pdf_path, page_num):
    pdf_doc = fitz.open(pdf_path)
    page = pdf_doc[page_num]
    tables = page.find_tables()

    if not tables:
        return None
    
