from pdf_preprocessing import pdf_to_markdown, pdf_to_markdown_chunks
from llm import LLMCallManager
from util import setup_environment, select_file, generate_dir, delete_dir
import logging


setup_environment()


logger = logging.getLogger(__name__)


def main():
    pdf_file_path = select_file()
    generate_dir()
    # pdf_to_markdown(pdf_file_path)
    pdf_to_markdown_chunks(pdf_file_path)


if __name__ == "__main__":
    main()