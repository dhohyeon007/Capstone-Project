from preprocessing import *
from llm import LLMCaller
from orchestrator import *
from util import *
import logging


setup_environment()

logger = logging.getLogger(__name__)


def main():
    # 1. 파일 선택
    pdf_file_path = select_file()

    try:
        # 2. 임시 파일 디렉토리 생성
        generate_dir()

        # 3. 텍스트 및 이미지 추출
        # pdf_to_markdown(pdf_file_path)
        pdf_to_markdown_chunks(pdf_file_path)

        schema = load_json_schema()

        orchestrator = ChunkProcessor(json_schema=schema)

        results = orchestrator.run_parallel_pipeline()

        if results:
            merged_result = orchestrator.merge_data(results)
    except Exception as e:
        logger.error("Terminating program.")
    # finally:
    #     delete_dir()


if __name__ == "__main__":
    main()