import pymupdf as fitz
import pymupdf4llm
import re
from pathlib import Path


data_dir_path = Path("data")
text_dir_path = data_dir_path / "texts"
image_dir_path = data_dir_path / "images"


def pdf_to_markdown(pdf_file_path):
    md_text = pymupdf4llm.to_markdown(
        pdf_file_path,
        write_images=True,
        image_path=str(image_dir_path),
        show_progress=True
    )
    page_count = len(fitz.open(pdf_file_path))
    text_file_path = text_dir_path / f"Markdown-{1}-{page_count}.md"
    text_file_path.write_text(md_text, encoding="utf-8")


def pdf_to_markdown_chunks(pdf_file_path, chunk_size=15 ,overlap=2):
    md_pages = pymupdf4llm.to_markdown(
        pdf_file_path,
        page_chunks=True,
        write_images=True,
        image_path=str(image_dir_path),
        show_progress=True
    )

    page_count = len(md_pages)
    stride = chunk_size - overlap
    for i in range(0, page_count, stride):
        start_page_num = i
        end_page_num = min(i + chunk_size, page_count)

        md_chunk_text = "\n\n".join([md_page["text"] for md_page in md_pages[start_page_num:end_page_num]])
        text_file_path = text_dir_path / f"Markdown-{start_page_num+1}-{end_page_num}.md"
        text_file_path.write_text(md_chunk_text, encoding="utf-8")

        if end_page_num == page_count:
            break


def construct_payload():
    text_path_list = list(text_dir_path.iterdir())
    image_path_list = list(image_dir_path.iterdir())
    payload = []

    if len(text_path_list) == 1:
        # [[text, [images]]]
        single_payload = []
        single_payload.append(text_path_list[0])
        single_payload.append(image_path_list)
        payload.append(single_payload)
        return payload
    
    else:
        # [[text, [images]], [text, [images]], ...]
        for text_path in text_path_list:
            text_path_split = text_path.stem.split("-")
            start_page_num = int(text_path_split[-2])
            end_page_num = int(text_path_split[-1])
            
            matched_images = []
            for image_path in image_path_list:
                image_path_split = image_path.stem.split("-")
                image_page_num = int(image_path_split[-2])
                if start_page_num <= image_page_num <= end_page_num:
                    matched_images.append(image_path)

            chunk_payload = []
            chunk_payload.append(text_path)
            chunk_payload.append(matched_images)
            payload.append(chunk_payload)
        return payload