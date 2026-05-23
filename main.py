from pathlib import Path
from sub import select_file, call_gemini_api
from PIL import Image
import os
import pymupdf4llm as p4l
import json
import sys
import time
import concurrent.futures
# import pandas as pd


def process_chunk(item, schema, prompt):
    chunk_id = item["chunk_id"]
    print(f"[{chunk_id}] 쓰레드 작업 시작...")

    contents = [prompt, item["text"]]
    if item["images"]:
        contents.extend(item["images"])

    try:
        response = call_gemini_api(contents, schema)
        if response.text:
            result_json = json.loads(response.text)
            print(f"[{chunk_id}] 추출 완료")

            return result_json
        
    except Exception as e:
        print(f"[{chunk_id}] 오류 발생: {e}")

        return {}
    

def merge_data(json_list, schema):
    json_str = json.dumps(json_list, ensure_ascii=False, indent=2)

    reduce_prompt = """
    """

    contents = [reduce_prompt, json_str]
    
    try:
        response = call_gemini_api(contents, schema)

        if response.text:
            print("병합 완료")
            return json.load(response.text)
    
    except Exception as e:
        print(f"병합 중 오류 발생: {e}")
        return {}


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
    pdf_name = Path(pdf_file_path).name

    print("PDF 마크다운 변환 및 이미지 추출 중...")
    md_pages = p4l.to_markdown(pdf_file_path,
                               page_chunks=True,
                               write_images=True,
                               image_path=str(image_dir)
                               )

    chunk_size = 7
    payload_queue = []

    print("텍스트 청킹 및 로컬 이미지 매핑 중...")
    for i in range(0, len(md_pages), chunk_size):
        chunk_batch = md_pages[i:i + chunk_size]

        md_chunks = [p["text"] for p in chunk_batch]
        merged_text = "\n\n---\n\n".join(md_chunks)

        start_page = i
        end_page = i + len(md_chunks) - 1

        md_file_path = text_dir / f"text_page{start_page + 1}-{end_page + 1}.md"
        md_file_path.write_text(merged_text, encoding="utf-8")

        valid_images = []

        for j in range(len(chunk_batch)):
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
            "chunk_id":f"{start_page}-{end_page}",
            "text": merged_text,
            "images": valid_images
            })
        
    schema_file_path = "extraction_schema.json"
    
    try:
        with open(schema_file_path, "r", encoding="utf-8") as f:
            external_schema = json.load(f)
            print(f"외부 스키마 로드 완료: {schema_file_path}")
    except FileNotFoundError:
        print(f"스키마 파일을 찾을 수 없습니다: {schema_file_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"스키마 파일의 JSON 형식이 잘못되었습니다.")
        sys.exit(1)

    map_prompt = """
    """

    print("병렬 데이터 추출 시작...")
    all_json_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        future_to_chunk = {executor.submit(process_chunk, item, external_schema, map_prompt): item for item in payload_queue}

        for future in concurrent.futures.as_completed(future_to_chunk):
            try:
                result_dict = future.result()
                if result_dict:
                    all_json_results.append(result_dict)
            except Exception as e:
                print("처리 중 오류 발생")

    print("데이터 병합 시작...")
    final_data = merge_data(all_json_results, external_schema)


if __name__ == "__main__":
    main()