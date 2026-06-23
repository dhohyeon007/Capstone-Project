from llm import LLMCaller
from preprocessing import construct_chunk
from google.genai import types
import mimetypes
import concurrent.futures
import json
import logging


logger = logging.getLogger(__name__)


class ChunkProcessor:
    def __init__(self, json_schema):
        self.llm_caller = LLMCaller()
        self.chunk_path_list = None
        self.json_schema = json_schema

        try:
            max_rpm = max([model['rpm'] for model in self.llm_caller.model_list])
            self.max_workers = min(max_rpm, 30)
        except AttributeError:
            self.max_workers = 15


    def load_chunk_path_list(self):
        self.chunk_path_list = construct_chunk()


    def path_to_payload(self, chunk):
        text_path = chunk['text']
        image_path_list = chunk['images']

        try:
            markdown_text = text_path.read_text(encoding="utf-8")
        except Exception as e:
            # throw to process_chunk()
            raise e

        image_list = []
        for image_path in image_path_list:
            try:
                mime_type, _ = mimetypes.guess_type(str(image_path))
                if not mime_type:
                    mime_type = "image/jpeg"

                image_bytes = image_path.read_bytes()

                part = types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type
                )
                image_list.append(part)
            except Exception as e:
                # throw to process_chunk()
                raise e

        return markdown_text, image_list
    

    def process_chunk(self, chunk, config):
        prompt = """ """
        try:
            markdown_text, image_list = self.path_to_payload(chunk)
            contents = [prompt, markdown_text] + image_list
            response = self.llm_caller.call_llm(contents, config)
            return response
        
        except Exception as e:
            # throw to run_parallel_pipeline()
            raise e
        

    def run_parallel_pipeline(self):
        if not self.chunk_path_list:
            self.load_chunk_path_list()

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=self.json_schema,
            temperature=0.0
        )

        results = []

        logger.info(f"Parallel pipeline started (# of threads: {self.max_workers})")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futuer_to_chunk = {
                executor.submit(self.process_chunk, chunk, config): chunk
                for chunk in self.chunk_path_list
            }

            for future in concurrent.futures.as_completed(futuer_to_chunk):
                chunk = futuer_to_chunk[future]
                chunk_name = chunk['text'].name

                try:
                    response = future.result()
                    results.append({
                        'file': chunk_name,
                        'response': response.text
                    })
                    logger.info(f"[{chunk_name}] extracted successfully.")

                except Exception as e:
                    logger.error(f"Error occured while processing [{chunk_name}]: {e}")
                    results.clear()
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise e
        
        return results

    
    def merge_data(self, results):
        prompt = """ """
        parsed_json_list = []
        for res in results:
            try:
                clean_str = res['response'].strip().removeprefix('```json').removesuffix('```')
                parsed_json_list.append(json.loads(clean_str))
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse data: {res['file']}")

        merged_json_str = json.dumps(parsed_json_list, ensure_ascii=False, indent=2)

        contents = [prompt, merged_json_str]

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=self.json_schema,
            temperature=0.0
        )

        final_response = self.llm_caller.call_llm(contents, config)

        with open('data.json', 'w', encoding='utf-8') as f:
            json.dump(json.loads(final_response.text), f, ensure_ascii=False, indent=2)
        logger.info("Saved merged JSON")

        return final_response