from pathlib import Path
from sub import select_file, LLMCallManager
from PIL import Image
from google.genai import types
import pymupdf as fitz
import pymupdf4llm as p4l
import json
import sys
import concurrent.futures
# import pandas as pd


def safe_to_markdown(pdf_file_path, image_dir):
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
                pages=[page_num],
                write_images=True,
                image_path=str(image_dir)
            )
            markdown_results.append(md_text)
        except Exception as e:
            if "invalid key in dict" in str(e).lower():
                print(f"{page_num + 1}번째 페이지 손상됨. 스킵합니다.")
            else:
                print(f"{page_num + 1}번째 페이지 알 수 없는 오류: {e}")

    return markdown_results


def chunk_contents(text_dir, image_dir, pdf_name, md_pages, chunk_size=7):
    payload_queue = []

    for i in range(0, len(md_pages), chunk_size):
        md_chunks = md_pages[i:i + chunk_size]

        merged_text = "\n\n---\n\n".join(md_chunks)

        start_page = i
        end_page = i + len(md_chunks) - 1

        md_file_path = text_dir / f"text_page{start_page + 1}-{end_page + 1}.md"
        md_file_path.write_text(merged_text, encoding="utf-8")

        valid_images = []

        for j in range(len(md_chunks)):
            absolute_page_num = i + j
            formatted_page = f"{absolute_page_num + 1:04d}"
            pattern = f"{pdf_name}-{formatted_page}-*.*"
            matched_files = list(image_dir.glob(pattern))

            for img_path in matched_files:
                try:
                    img_obj = Image.open(img_path)
                    valid_images.append(img_obj)
                except Exception as e:
                    print(f"이미지 로드 실패 ({img_path.name})")

        payload_queue.append({
            "chunk_id":f"{start_page+1}-{end_page+1}",
            "text": merged_text,
            "images": valid_images
            })
        
        return payload_queue


def load_json_schema():
    schema_file_path = "extraction_schema.json"
    
    try:
        with open(schema_file_path, "r", encoding="utf-8") as f:
            json_schema = json.load(f)
            print(f"외부 스키마 로드 완료: {schema_file_path}")
            return json_schema
    except FileNotFoundError:
        print(f"스키마 파일을 찾을 수 없습니다: {schema_file_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"스키마 파일의 JSON 형식이 잘못되었습니다.")
        sys.exit(1)


def extract_data(llm_manager, item, schema):
    llm_manager = llm_manager

    chunk_id = item["chunk_id"]
    print(f"[{chunk_id}] 쓰레드 작업 시작...")

    prompt = """
    제공된 JSON 스키마에 따라 정확하게 데이터를 추출하시오.
    """

    contents = [prompt, item["text"]]
    if item["images"]:
        contents.extend(item["images"])

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.0
    )

    try:
        response = llm_manager.call_llm_api('gemini-3.5-flash', contents, config)
        if response.text:
            result_json = json.loads(response.text)
            print(f"[{chunk_id}] 추출 완료")

            return result_json
        
    except Exception as e:
        print(f"[{chunk_id}] 오류 발생: {e}")

        return {}
    

def merge_data(llm_manager, json_list, schema):
    json_str = json.dumps(json_list, ensure_ascii=False, indent=2)

    prompt = """
    제공된 JSON 스키마에 따라 정확하게 데이터를 병합하시오.
    """

    contents = [prompt, json_str]

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.0
    )

    try:
        response = llm_manager.call_llm_api('gemma-4-26b-a4b-it', contents, config)

        if response.text:
            print("병합 완료")
            return json.loads(response.text)
    
    except Exception as e:
        print(f"병합 중 오류 발생: {e}")
        return {}


def main():
    parent_dir = Path("data")
    text_dir = parent_dir / "text"
    image_dir = parent_dir / "images"

    parent_dir.mkdir(exist_ok=True)
    text_dir.mkdir(exist_ok=True)
    image_dir.mkdir(exist_ok=True)

    pdf_file_path = select_file()
    pdf_name = Path(pdf_file_path).name

    print("PDF 마크다운 변환 및 이미지 추출 중...")
    md_pages = safe_to_markdown(pdf_file_path, image_dir)

    print("텍스트 청킹 및 로컬 이미지 매핑 중...")
    payload_queue = chunk_contents(text_dir, image_dir, pdf_name, md_pages)    

    print("JSON 스키마 로드 중...")
    json_schema = load_json_schema()

    llm_manager = LLMCallManager()

    print("병렬 데이터 추출 시작...")
    all_json_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_chunk = {executor.submit(extract_data, llm_manager, item, json_schema): item for item in payload_queue}

        for future in concurrent.futures.as_completed(future_to_chunk):
            try:
                result_dict = future.result()
                if result_dict:
                    all_json_results.append(result_dict)
            except Exception as e:
                print("처리 중 오류 발생")

    print("데이터 병합 시작...")
    final_data = merge_data(llm_manager, all_json_results, json_schema)

    with open('final_data', 'r', encoding='utf-8') as file:
        json.dump(final_data, file, ensure_ascii=False, indent=4)

    for filepath in text_dir.iterdir():
        if filepath.is_file():
            filepath.unlink()
    text_dir.rmdir()

    for filepath in image_dir.iterdir():
        if filepath.is_file():
            filepath.unlink()
    image_dir.rmdir()

    parent_dir.rmdir()


if __name__ == "__main__":
    main()