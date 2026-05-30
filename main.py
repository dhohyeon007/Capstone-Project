from pathlib import Path
from sub import LLMCallManager, select_file, prologue, epilogue
from PIL import Image
from google.genai import types
import pymupdf as fitz
import pymupdf4llm as p4l
import logging
import json
import sys
import concurrent.futures
# import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler("Project.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


fitz.TOOLS.mupdf_display_errors(False)


def chunk_contents(text_dir, image_dir, pdf_name, md_pages, chunk_size=7):
    """페이지 단위 청크 분할 및 이미지 매핑"""
    payload_queue = []

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
                    logger.warning(f"이미지 로드 실패 ({img_path.name})")

        payload_queue.append({
            "chunk_id":f"{start_page+1}-{end_page+1}",
            "text": merged_text,
            "images": valid_images
            })
        
    return payload_queue


def load_json_schema():
    """스키마 파일 로드"""
    schema_file_path = "extraction_schema.json"
    
    try:
        with open(schema_file_path, "r", encoding="utf-8") as f:
            json_schema = json.load(f)
            logger.info(f"외부 스키마 로드 완료: {schema_file_path}")
            return json_schema
    except FileNotFoundError as fe:
        logger.error(f"스키마 파일을 찾을 수 없습니다: {schema_file_path}")
        epilogue()
        raise fe
    except json.JSONDecodeError as je:
        logger.error(f"스키마 파일의 JSON 형식이 잘못되었습니다.")
        epilogue()
        raise je


def extract_data(llm_manager, item, schema, json_dir):
    """청크로부터 JSON 형태의 데이터 추출"""
    llm_manager = llm_manager

    chunk_id = item["chunk_id"]
    logger.info(f"[{chunk_id}] 쓰레드 작업 시작...")

    prompt = """
    제공된 JSON 스키마에 따라 정확하게 데이터를 추출하시오.

    [데이터 전처리 및 보정 지침]
    제공된 마크다운 텍스트는 PDF에서 기계적으로 추출되었기 때문에 시각적 레이아웃 파편(오류)이 포함되어 있습니다. 데이터를 추출할 때 다음 규칙을 반드시 적용하십시오.
    
    1. 거짓 헤딩(False Heading) 무시: 긴 URL이나 참고문헌 텍스트가 줄바꿈되면서, 의미 없는 문장 파편이나 단어 앞에 `## ` (헤딩 기호)가 잘못 붙은 경우가 있습니다. (예: `## CIties 홈페이지)`, `## e-emergency`).
    2. 문맥 연결: 이러한 거짓 헤딩은 새로운 섹션의 시작이 아닙니다. 해당 기호를 무시하고 바로 윗줄의 텍스트나 URL과 이어지는 내용으로 취급하여 데이터를 해석하십시오.
    3. 데이터 정제: JSON 스키마에 맞게 데이터를 추출할 때, 최종 결과물에는 불필요한 마크다운 기호가 포함되지 않도록 깔끔한 텍스트로 정제하십시오.
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
        response = llm_manager.call_llm_api(contents, config)
        if response.text:
            result_json = json.loads(response.text)
            logger.info(f"[{chunk_id}] 추출 완료")

            # DEBUG
            json_path = json_dir / f"chunk_{chunk_id}.json"
            json_path.write_text(response.text, encoding="utf-8")

            return result_json
        
    except Exception as e:
        print(f"[{chunk_id}] 오류 발생: {e}")
        raise e
    

def merge_data(llm_manager, json_list, schema):
    """추출된 JSON 형태의 데이터 병합"""
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
        response = llm_manager.call_llm_api(contents, config)

        if response.text:
            logger.info("병합 완료")
            return json.loads(response.text)
    
    except Exception as e:
        logger.warning(f"병합 중 오류 발생: {e}")
        return {}


def main():
    text_dir, image_dir, json_dir = prologue()

    pdf_file_path = select_file()
    pdf_name = Path(pdf_file_path).name

    md_pages = p4l.to_markdown(
        pdf_file_path,
        page_chunks=True,
        write_images=True,
        image_path=str(image_dir),
        show_progress=True
    )

    logger.info("텍스트 청킹 및 로컬 이미지 매핑 중...")
    payload_queue = chunk_contents(text_dir, image_dir, pdf_name, md_pages)    

    logger.info("JSON 스키마 로드 중...")
    json_schema = load_json_schema()

    llm_manager = LLMCallManager()

    logger.info("병렬 데이터 추출 시작...")
    all_json_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_chunk = {executor.submit(extract_data, llm_manager, item, json_schema, json_dir): item for item in payload_queue}

        for future in concurrent.futures.as_completed(future_to_chunk):
            try:
                result_dict = future.result()
                if result_dict:
                    all_json_results.append(result_dict)
            except Exception as e:
                logger.error(f"처리 중 오류 발생: {e}")
                logger.info("임시 파일을 안전하게 정리하고 종료합니다.")
                epilogue()
                sys.exit(1)

    logger.info("데이터 병합 시작...")
    final_data = merge_data(llm_manager, all_json_results, json_schema)

    final_data_str = json.dumps(final_data, ensure_ascii=False, indent=4)
    json_path = json_dir / f"{pdf_name}.json"
    json_path.write_text(final_data_str, encoding="utf-8")

    epilogue()


if __name__ == "__main__":
    main()