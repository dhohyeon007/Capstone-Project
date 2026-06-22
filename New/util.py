import os
import sys
import json
import logging
import pymupdf as fitz
import shutil
from pathlib import Path


def setup_environment():
    """프로그램 실행 시 1회 호출되어 로깅 및 외부 라이브러리 전역 설정을 담당"""
    file_handler = logging.FileHandler("Project.log", encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)

    file_formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
    file_handler.setFormatter(file_formatter)

    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler]
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    
    fitz.TOOLS.mupdf_display_errors(False)


logger = logging.getLogger(__name__)


def select_file():
    """선택한 파일의 경로 반환"""
    current_dir = os.getcwd()

    while True:
        items = [
            entry.name for entry in os.scandir(current_dir)
            if entry.name.endswith(".pdf") or entry.is_dir()
        ]
        print(f"현재 디렉토리: {current_dir}")
        print("0. ..")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item}")

        choice = input("파일 선택 혹은 디렉토리 이동 (숫자 입력): ")
        if choice == "-1":
            # epilogue()
            sys.exit(0)
        elif choice == "0":
            current_dir = os.path.dirname(current_dir)
        else:
            try:
                target_path = os.path.join(current_dir, items[int(choice) - 1])
                if os.path.isdir(target_path):
                    current_dir = target_path
                else:
                    return target_path
            except (ValueError, IndexError):
                print("다시 시도하십시오.")


def load_json_schema():
    schema_file_path = "schema.json"
    
    try:
        with open(schema_file_path, "r", encoding="utf-8") as f:
            json_schema = json.load(f)
            logger.info(f"외부 스키마 로드 완료: {schema_file_path}")
            return json_schema
    except FileNotFoundError as fe:
        logger.error(f"스키마 파일을 찾을 수 없습니다: {schema_file_path}")
        raise fe
    except json.JSONDecodeError as je:
        logger.error(f"스키마 파일의 JSON 형식이 잘못되었습니다.")
        raise je
    

data_dir_path = Path("data")
text_dir_path = data_dir_path / "texts"
image_dir_path = data_dir_path / "images"


def generate_dir():
    data_dir_path.mkdir(exist_ok=True)
    text_dir_path.mkdir(exist_ok=True)
    image_dir_path.mkdir(exist_ok=True)


def delete_dir():
    if data_dir_path.exists() and data_dir_path.is_dir():
        try:
            shutil.rmtree(data_dir_path)
            logger.info("\'data\' 디렉토리 삭제 완료.")
        except Exception as e:
            logger.error(f"디렉토리 삭제 중 오류 발생: {e}")