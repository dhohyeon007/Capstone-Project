import pymupdf4llm
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
    text_file_path = text_dir_path / "Markdown.md"
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
        text_file_path = text_dir_path / f"Markdown_{start_page_num+1}-{end_page_num}.md"
        text_file_path.write_text(md_chunk_text, encoding="utf-8")

        if end_page_num == page_count:
            break