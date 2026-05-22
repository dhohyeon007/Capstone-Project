from google import genai
import os
# import sys
# import time
# import pandas as pd
import pdfplumber
import pymupdf as fitz
import pymupdf4llm as p4l
from pathlib import Path
from sub import select_file


# client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))


def main():
    parent_dir = Path("data")
    text_dir = parent_dir / "text"
    image_dir = parent_dir / "images"
    # table_dir = parent_dir / "tables"

    parent_dir.mkdir(exist_ok=True)
    text_dir.mkdir(exist_ok=True)
    image_dir.mkdir(exist_ok=True)
    # table_dir.mkdir(exist_ok=True)

    pdf_file_path = select_file()
    md_pages = p4l.to_markdown(pdf_file_path,
                               page_chunks=True,
                               write_images=True,
                               image_path=str(image_dir)
                               )

    chunk_size = 7
    for i in range(0, len(md_pages), chunk_size):
        md_chunks = [p["text"] for p in md_pages[i:i + chunk_size]]
        merged_text = "\n\n---\n\n".join(md_chunks)
        start_page = i
        end_page = i + len(md_chunks) - 1
        md_file_path = text_dir / f"text_page{start_page}-{end_page}.md"
        md_file_path.write_text(merged_text, encoding="utf-8")


if __name__ == "__main__":
    main()