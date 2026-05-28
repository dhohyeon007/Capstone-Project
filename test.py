from pathlib import Path
from sub import select_file
import pymupdf as fitz
import pymupdf4llm as p4l
import sys


fitz.TOOLS.mupdf_display_errors(False)


def main():
    pdf_file_path = select_file()

    print("PDF 마크다운 변환 및 이미지 추출 중...")
    try:
        pdf_doc = fitz.open(pdf_file_path)
        total_pages = len(pdf_doc)
    except Exception as e:
        print(f"파일을 열 수 없습니다: {e}")
        sys.exit(1)

    markdown_results = []

    for page_num in range(total_pages):
        try:
            md_text = p4l.to_markdown(
                pdf_file_path,
                pages=[page_num]
            )
            markdown_results.append(md_text)
            warning = fitz.TOOLS.mupdf_warnings()
            if warning:
                if "invalid key in dict" in warning.lower():
                    print(f"{page_num + 1}번째 페이지 손상됨. 스킵합니다.")
        except Exception as e:
            print(f"{page_num + 1}번째 페이지 알 수 없는 오류: {e}")

    merged_text = "\n\n---\n\n".join(markdown_results)

    Path("temp_markdown.md").write_text(merged_text, encoding="utf-8")


if __name__ == "__main__":
    main()