"""
Parallel Chunk to JSON Converter
"""


from llm import LLMCaller
from preprocessing import construct_chunk
from google.genai import types
import mimetypes
import concurrent.futures
import json
import logging


logger = logging.getLogger(__name__)


class ChunkProcessor:
    def __init__(self, json_schema, text_dir_path, image_dir_path, json_dir_path):
        self.llm_caller = LLMCaller()
        self.path_chunk_list = None
        self.json_schema = json_schema
        
        self.text_dir_path = text_dir_path
        self.image_dir_path = image_dir_path
        self.json_dir_path = json_dir_path

        try:
            max_rpm = max([model['rpm'] for model in self.llm_caller.model_list])
            self.max_workers = min(max_rpm, 30)
        except AttributeError:
            self.max_workers = 15


    def load_path_chunk_list(self):
        self.path_chunk_list = construct_chunk(self.text_dir_path, self.image_dir_path)


    def path_to_payload(self, path_chunk):
        """Path 객체 형태의 청크를 LLM 이 인식 가능한 실제 데이터(페이로드)로 변환"""
        text_path = path_chunk['text']
        image_path_list = path_chunk['images']

        # text
        try:
            markdown_text = text_path.read_text(encoding="utf-8")
        except Exception as e:
            # throw to process_chunk()
            raise e

        # images
        image_list = []
        for image_path in image_path_list:
            try:
                # MIME type
                mime_type, _ = mimetypes.guess_type(str(image_path))
                if not mime_type:
                    mime_type = "image/jpeg"

                # image bytes
                image_bytes = image_path.read_bytes()

                # MIME type + image bytes
                image = types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type
                )
                image_list.append(image)
            except Exception as e:
                # throw to process_chunk()
                raise e

        return markdown_text, image_list
    

    def process_chunk(self, path_chunk, config):
        """Path 객체로 구성된 청크를 페이로드로 변환 후 LLM으로 처리"""
        prompt = """
        당신은 지자체 공문서에서 탄소중립 녹색성장 데이터를 정확하게 추출하는 데이터 엔지니어입니다.
        제공된 텍스트와 이미지를 분석하여 주어진 JSON 스키마에 맞게 데이터를 추출하세요.

        [추출 규칙]
        1. 누락 방지: 정보가 명확하지 않은 경우 임의로 추론하지 말고 null 로 처리하세요.
        2. 용어 통일: 부서명이나 사업명은 문서에 등장하는 공식 명칭(Full name)을 그대로 사용하세요. (예: '환경과' -> '기후환경과'로 축약/변형 금지)
        3. 단위 엄수: 예산(백만원, 억원) 및 온실가스 감축량(천톤CO2eq 등)의 단위를 스키마의 요구사항에 맞게 변환하여 숫자만 기입하세요.
        4. 문맥 추론: 표가 여러 페이지에 걸쳐 나뉘어 있더라도 문맥을 파악하여 하나의 배열(Array) 객체로 완성하세요.
        """
        try:
            markdown_text, image_list = self.path_to_payload(path_chunk)
            contents = [prompt, markdown_text] + image_list
            response = self.llm_caller.call_llm(contents, config)
            return response
        
        except Exception as e:
            # throw to run_parallel_pipeline()
            raise e
        

    def run_pipeline(self):
        if not self.path_chunk_list:
            self.load_path_chunk_list()

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=self.json_schema,
            temperature=0.0
        )

        results = []

        # w/o chunking
        if len(self.path_chunk_list) == 1:
            path_chunk = self.path_chunk_list[0]
            chunk_name = path_chunk['text'].stem

            try:
                response = self.process_chunk(path_chunk, config)
                results.append({
                    'file':chunk_name,
                    'response':response
                })
                logger.info(f"[{chunk_name}] Extracted successfully")

            except Exception as e:
                logger.error(f"Error occured while processing [{chunk_name}.md]")
                results.clear()
                raise e

        # w/ chunking
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_chunk = {
                    executor.submit(self.process_chunk, path_chunk, config): path_chunk
                    for path_chunk in self.path_chunk_list
                }

                for future in concurrent.futures.as_completed(future_to_chunk):
                    path_chunk = future_to_chunk[future]
                    chunk_name = path_chunk['text'].stem

                    try:
                        response = future.result()
                        results.append({
                            'file':chunk_name,
                            'response':response.text
                        })
                        logger.info(f"[{chunk_name}] Extracted successfully")
                    
                    except Exception as e:
                        logger.error(f"Error occured while processing [{chunk_name}.md]")
                        results.clear()
                        executor.shutdown(wait=False, cancel_futures=True)
                        raise e
                    
        json_dict = self.asdf(results)
        
        return json_dict
    

    def merge_and_save(self, results):
        if len(results) == 1:
            final_result = results[0]
        else:
            final_result = self.merge_json(results)
        
        self.save_to_json(final_result)

        clean_json_str = final_result['response'].strip().removeprefix('```json').removesuffix('```')

        final_json = json.loads(clean_json_str)

        return final_json

    
    def merge_json(self, results):
        prompt = """
        당신은 여러 개의 JSON 데이터를 하나로 통합하는 데이터 정제 전문가입니다.
        제공된 JSON 배열은 긴 문서를 페이지 단위로 나누어 병렬 추출한 결과물이며, 청크 간의 오버랩(Overlap)으로 인해 중복된 데이터나 다른 용어로 표현된 동일한 내용이 존재할 수 있습니다.

        [병합 규칙]
        1. 중복 제거 및 식별: 'task_name(사업명)'이나 'sector(부문)'의 맥락이 실질적으로 동일한 항목은 하나의 객체로 병합하세요.
        2. 정보 결합: 분할된 청크에서 한쪽에는 예산 정보만 있고, 다른 쪽에는 감축량 정보만 있는 경우, 이를 하나의 완성된 객체로 결합하세요.
        3. 충돌 해결: 동일한 필드에 대해 서로 다른 수치나 내용이 존재할 경우, 더 구체적이고 상세한 내용을 포함한 데이터를 우선적으로 채택하세요.
        4. 스키마 준수: 최종 출력물은 반드시 제공된 단일 JSON 스키마 구조를 엄격하게 준수해야 합니다.
        """
        page_count = 1
        parsed_json_list = []
        for res in results:
            try:
                page_count = max(page_count, res['file'].split('-')[2])
                clean_str = res['response'].strip().removeprefix('```json').removesuffix('```')
                parsed_json_list.append(json.loads(clean_str))
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON: {res['file']}.json")

        # Serialization
        json_list_str = json.dumps(parsed_json_list, ensure_ascii=False, indent=2)

        contents = [prompt, json_list_str]

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=self.json_schema,
            temperature=0.0
        )

        merged_response = self.llm_caller.call_llm(contents, config)
        merged_result = {
            'file':f"Chunk-1-{page_count}",
            'response':merged_response.text
        }

        return merged_result
    

    def save_to_json(self, result):
        try:
            chunk_name = result['file']
            response_text = result['response']

            # Deserialization for JSON format verification
            clean_text = response_text.strip().removeprefix('```json').removesuffix('```')
            final_data = json.loads(clean_text)

            json_file_path = self.json_dir_path / f"{chunk_name}.json"

            with json_file_path.open('w', encoding='utf-8') as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved JSON data [{chunk_name}.json]")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to load JSON string: {e}")
            raise e