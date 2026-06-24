from preprocessing import *
from chunk_processor import *
from util import *
import logging


setup_environment()

logger = logging.getLogger(__name__)


def main():
    # 1. 파일 선택
    pdf_file_path = select_file()

    try:
        # 2. 임시 파일 디렉토리 생성
        data_dir_path, text_dir_path, image_dir_path, json_dir_path = generate_dir()

        # 3. 텍스트 및 이미지 추출
        # pdf_to_markdown(pdf_file_path)
        pdf_to_markdown_chunks(pdf_file_path, text_dir_path, image_dir_path)

        schema = load_json_schema()

        chunk_processor = ChunkProcessor(schema, text_dir_path, image_dir_path, json_dir_path)

        json_dict = chunk_processor.run_pipeline()

        print(json_dict)

    except Exception as e:
        logger.error("Terminating program.")
    # finally:
    #     delete_dir(data_dir_path)


if __name__ == "__main__":
    main()