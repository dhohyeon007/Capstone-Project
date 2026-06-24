"""
PDF Document Preprocessing
"""


import pymupdf as fitz
import pymupdf4llm


def pdf_to_markdown(pdf_file_path, text_dir_path, image_dir_path):
    """단일 마크다운 파일 생성"""
    
    md_text = pymupdf4llm.to_markdown(
        pdf_file_path,
        write_images=True,
        image_path=str(image_dir_path),
        show_progress=True
    )

    page_count = len(fitz.open(pdf_file_path))
    text_file_path = text_dir_path / f"Chunk-{1}-{page_count}.md"
    text_file_path.write_text(md_text, encoding="utf-8")


def pdf_to_markdown_chunks(pdf_file_path, text_dir_path, image_dir_path, chunk_size=15 ,overlap=2):
    """페이지 오버랩 적용된 마크다운 청크 파일 생성"""
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
        text_file_path = text_dir_path / f"Chunk-{start_page_num+1}-{end_page_num}.md"
        text_file_path.write_text(md_chunk_text, encoding="utf-8")

        if end_page_num == page_count:
            break


def construct_chunk(text_dir_path, image_dir_path):
    """Path 객체 형태의 [텍스트, 이미지 리스트] 청크 구성"""
    text_path_list = list(text_dir_path.iterdir())
    image_path_list = list(image_dir_path.iterdir())
    chunk_path_list = []

    if len(text_path_list) == 1:
        single_chunk = {}
        single_chunk['text'] = text_path_list[0]
        single_chunk['images'] = image_path_list
        chunk_path_list.append(single_chunk)
        return chunk_path_list
    
    else:
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

            chunk = {}
            chunk['text'] = text_path
            chunk['images'] = matched_images
            chunk_path_list.append(chunk)
        return chunk_path_list