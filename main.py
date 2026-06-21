from pathlib import Path
from sub import setup_environment, LLMCallManager, select_file, prologue, epilogue
from google.genai import types
import pymupdf4llm as p4l
import logging
import json
import re
import sys
import mimetypes
import concurrent.futures
# import pandas as pd


setup_environment()

logger = logging.getLogger(__name__)


def toc_extraction(llm_manager, md_pages):
    """최초 1회 실행: 문서 앞부분(목차)을 읽어 트리 구조 생성"""
    toc_text = "\n\n---\n\n".join([p["text"] for p in md_pages[:15]])

    prompt = """
    [역할]
    당신은 방대한 공공 문서의 목차(Table of Contents) 텍스트를 분석하여, 문서의 '계층적 트리 구조(Hierarchy)'와 '페이지 맵(Page Map)'을 정확하게 추출하는 무결성 데이터 파싱 엔진입니다.

    [작업 지시]
    입력된 목차 마크다운 텍스트를 분석하여 각 섹션의 상하위 계층 구조를 파악하고, 시작 페이지와 끝 페이지를 계산하여 엄격한 JSON 형태로 출력하십시오.

    [출력 JSON 구조 예시]
    {
    "page_1_5": "Ⅰ. 계획의 개요",
    "page_6_59": "Ⅱ. 지역 특성 및 배출 현황",
    "page_60_69": "Ⅵ. 기본계획 추진과제 > 1. 감축 대책 > 1-1. 건물 부문",
    "page_70_78": "Ⅵ. 기본계획 추진과제 > 1. 감축 대책 > 1-2. 수송 부문"
    }

    [절대 준수 규칙 - 위반 시 시스템 치명적 오류 발생]
    1. 계층 연결(Breadcrumb): 대분류, 중분류, 소분류 등 종속 관계를 파악하여 ` > ` 기호로 연결한 단일 문자열로 만드십시오. (단일 계층일 경우 그대로 출력)
    2. 페이지 범위(Range) 계산: 
    - 목차에 명시된 해당 섹션의 '시작 페이지'부터, '다음 섹션이 시작되기 직전 페이지'까지를 해당 섹션의 범위(`page_시작_끝`)로 계산하십시오.
    - 하위 계층(소분류)이 존재하는 경우, 상위 계층(대분류)의 단독 페이지 범위는 생성하지 마십시오. 가장 텍스트가 밀집된 최하위 계층(Leaf Node)을 기준으로 매핑하십시오.
    3. 표 목차(List of Tables)와 그림 목차(List of Figures) 섹션에 나열된 모든 항목은 문서의 논리적 뼈대가 아니므로 파싱 대상에서 완벽히 제외하십시오. 오직 텍스트 본문의 목차만 추출하십시오.
    4. 노이즈 제거: "목차", "Page", 점선("....") 등 구조와 무관한 OCR 파편이나 시각적 기호는 완전히 무시하십시오.
    5. 순수 JSON 출력: 어떠한 설명, 인사말, 마크다운 코드 블록(```json) 표기 없이 오직 유효한 JSON 객체 하나만 출력하십시오.
    """

    contents = [prompt, toc_text]

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        temperature=0.0
    )

    response = llm_manager.call_llm_api(contents, config)

    if response and response.text:
        return json.loads(response.text)
    return {}


def get_context_for_chunk(start_page, end_page, toc_json):
    """현재 청크의 페이지 번호가 속한 계층(Context)을 찾아 반환"""
    contexts_found = []

    for page_range, hierarchy in toc_json.items():

        match = re.match(r"page_(\d+)_(\d+)", page_range)
        if match:
            start_p, end_p = int(match.group(1)), int(match.group(2))

            if max(start_page, start_p) <= min(end_page, end_p):
                if hierarchy not in contexts_found:
                    contexts_found.append(hierarchy)
            
    if not contexts_found:
        return ["알 수 없는 부문 (문맥 추론 필요)"]
        
    return contexts_found


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
                    mime_type, _ = mimetypes.guess_type(str(img_path))
                    if not mime_type:
                        mime_type = "image/jpeg"

                    image_bytes = img_path.read_bytes()

                    part = types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=mime_type
                    )
                    valid_images.append(part)
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
    schema_file_path = "schema.json"
    
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


def extract_data(llm_manager, item, schema, json_dir, toc_json):
    """청크로부터 JSON 형태의 데이터 추출"""
    start_p, end_p = map(int, item["chunk_id"].split("-"))
    contexts = get_context_for_chunk(start_p, end_p, toc_json)
    contexts_str = "\n".join(contexts)

    chunk_id = item["chunk_id"]
    logger.info(f"[{chunk_id}] 쓰레드 작업 시작...")

    prompt = f"""
    제공된 JSON 스키마에 따라 정확하게 데이터를 추출하시오.

    [CRITICAL CONTEXT]
    이 청크의 원본 데이터는 문서의 다음 섹션(들)에 걸쳐 있습니다:
    {contexts_str}

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
            json_str = json.dumps(result_json, ensure_ascii=False, indent=4)
            json_path = json_dir / f"chunk_{chunk_id}.json"
            json_path.write_text(json_str, encoding="utf-8")

            return result_json
        
    except Exception as e:
        print(f"[{chunk_id}] 오류 발생: {e}")
        raise e
    

def merge_data(llm_manager, json_list, schema):
    """추출된 JSON 형태의 데이터 병합"""
    
    json_str = json.dumps(json_list, ensure_ascii=False, separators=(',', ':'))

    prompt = """
    [역할]
    당신은 데이터 손실 없이 JSON을 병합하는 '무결성 데이터 파이프라인 엔진'입니다.

    [작업]
    입력된 여러 개의 JSON 데이터(리스트 형식)를 제공된 최종 JSON 스키마에 맞게 단일 JSON으로 완벽하게 병합하십시오.

    [절대 준수 규칙 - 위반 시 치명적인 시스템 오류 발생]
    1. 무손실 병합(Lossless): 입력된 원본 텍스트의 단어 하나, 조사 하나라도 절대 요약, 생략, 축약하지 마십시오. 100% 원본 그대로 복사(Copy & Paste)해야 합니다.
    2. 자의적 해석 금지: 문맥을 자연스럽게 만들기 위해 문장을 임의로 연결하거나 재구성하지 마십시오. 원본이 파편화된 문장이더라도 그대로 유지하십시오.
    3. 배열(Array) 누적: 동일한 키(Key)에 여러 값이 들어갈 수 있는 배열 형태인 경우, 기존 요소들을 덮어쓰거나 대표값 하나로 퉁치지 말고, 모든 요소를 순서대로 누적(Append/Extend) 하십시오.
    4. 데이터 창조 금지: 최종 스키마에 정의되어 있더라도, 원본 데이터에 없는 내용이라면 임의의 텍스트를 지어내지 말고 `null` 또는 빈 문자열(`""`), 빈 배열(`[]`)로 처리하십시오.
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

    llm_manager = LLMCallManager()

    logger.info("문서 계층 구조 파싱 중...")
    toc_json = toc_extraction(llm_manager, md_pages)

    logger.info("텍스트 청킹 및 로컬 이미지 매핑 중...")
    payload_queue = chunk_contents(text_dir, image_dir, pdf_name, md_pages)    

    logger.info("JSON 스키마 로드 중...")
    json_schema = load_json_schema()

    logger.info("병렬 데이터 추출 시작...")
    all_json_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_chunk = {executor.submit(extract_data, llm_manager, item, json_schema, json_dir, toc_json): item for item in payload_queue}

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