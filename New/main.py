from llm import LLMCaller
from util import *
from pdf_preprocessing import *
from chunk_processing import *
import logging


setup_environment()

logger = logging.getLogger(__name__)


def main():
    # 1. 파일 선택
    pdf_file_path = select_file()

    # 2. 임시 파일 디렉토리 생성
    generate_dir()

    # 3. 텍스트 및 이미지 추출
    # pdf_to_markdown(pdf_file_path)
    pdf_to_markdown_chunks(pdf_file_path)

    # 4. 페이로드 구성
    payload_list = construct_payload()

    llm_caller = LLMCaller()


if __name__ == "__main__":
    main()