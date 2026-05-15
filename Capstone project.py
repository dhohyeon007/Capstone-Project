from google import genai
from google.genai import types
import time
import os
import sys
import io
import shutil
import fitz  # PyMuPDF
import concurrent.futures


# Google GenAI 클라이언트 초기화
client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))


# 파일 업로드 함수
def upload_file():
    current_dir = os.getcwd()
    while True:
        print(f"Current Directory: {current_dir}")
        items = os.listdir(current_dir)
        print("0. .. (Go to parent directory)")
        for i, item in enumerate(items, 1):
            print(f"{i}. {item}")

        # 사용자 입력 처리
        choice = input("Select a file or directory (enter number): ")
        if choice == "-1":
            sys.exit(0)
        elif choice == "0":
            current_dir = os.path.dirname(current_dir)
        else:
            try:
                index = int(choice) - 1
                selected_item = items[index]
                if os.path.isdir(selected_item):
                    current_dir = os.path.join(current_dir, selected_item)
                else:
                    return os.path.join(current_dir, selected_item)
            except (ValueError, IndexError):
                print("Invalid choice. Please try again.")


# PDF 파일을 청크로 분할하는 함수
def split_pdf(file_path):
    doc = fitz.open(file_path)
    total_pages = len(doc)
    chunk_size = 10
    ranges = [(i, min(i + chunk_size, total_pages)) for i in range(0, total_pages, chunk_size)]
    chunks = []
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    dir_path = os.path.join(os.getcwd(), "temp_ocr")
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    
    for i, (start, end) in enumerate(ranges):
        chunk_doc = fitz.open()
        chunk_doc.insert_pdf(doc, from_page=start, to_page=end - 1)
        chunk_path = os.path.join(dir_path, f"{base_name}_part_{i + 1}.pdf")
        chunk_doc.save(chunk_path)
        chunk_doc.close()
        chunks.append(chunk_path)

    doc.close()
    start_page_nums = [start + 1 for start, _ in ranges]  # 각 청크의 시작 페이지 번호 계산
    return chunks, start_page_nums


# 각 청크를 처리하는 함수
def process_chunk(filepath, start_page_num, retry_count=3):
    output_file_name = os.path.splitext(filepath)[0] + "_OCR.md"
    
    for i in range(retry_count):
        try:
            # 파일 업로드
            uploaded_file = client.files.upload(file=filepath)

            # 파일 처리 완료 대기
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(2)
                uploaded_file = client.files.get(name=uploaded_file.name)

            # 프롬프트 정의
            prompt = f"""
            제공된 파일을 읽고 다음 규칙에 따라 텍스트를 추출하여 마크다운(Markdown) 형식으로 출력하세요:

            1. 본문 텍스트만 추출: 각 페이지 하단이나 문장 끝에 붙는 `` 형식의 태그나 -1829, 1830-과 같은 시스템 참조 번호는 모두 제외하고 보고서 본문의 텍스트만 있는 그대로 추출할 것.
            2. 페이지 구분: 각 페이지는 # Page 번호 형태의 헤더로 구분할 것.
            3. 요약 금지: 내용을 요약하지 말고 본문의 문구와 표 내용을 최대한 유지하여 작성할 것.
            4. 레이아웃 평탄화 및 데이터 직렬화: 표(Table)나 다단 레이아웃을 무리하게 시각적인 표 형식으로 복원하려 하지 말 것. 대신, 각 행과 열의 데이터를 논리적인 순서에 따라 평탄화(Flattening)하여 나열할 것.
            5. 대화형 문구 금지: "요약한 내용입니다", "정리해 드립니다"와 같은 서론이나 "도움이 되길 바랍니다" 같은 결론 문구를 절대 포함하지 말 것. 오직 추출된 본문만 출력할 것.
            6. 현재 제공된 파일의 첫 번째 페이지는 원본 문서의 {start_page_num} 페이지부터 시작한다는 점을 고려하여 페이지 번호를 정확히 매길 것.
            """

            # 모델에 프롬프트와 업로드된 파일을 전달하여 텍스트 추출
            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[prompt, uploaded_file],
            )

            dir_path = os.path.join(os.getcwd(), "temp_ocr")
            save_path = os.path.join(dir_path, output_file_name)
            if response.text:
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(response.text)
            else:
                if os.path.exists(save_path):
                    os.remove(save_path)  # 내용이 없는 파일은 삭제

        except Exception as e:
            if '429' in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                # print(e)
                wait_time = 60 + (i * 10)  # 지수적 백오프
                print(f"Rate limit exceeded. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Error processing {filepath}: {e}")
                break
        

# 분할된 청크 파일들을 병합하는 함수
def merge_markdown_files():
    # temp_ocr 디렉토리에서 모든 _OCR.md 파일을 찾아서 페이지 번호 순서대로 병합
    dir_path = os.path.join(os.getcwd(), "temp_ocr")
    md_files = sorted([f for f in os.listdir(dir_path) if f.endswith("_OCR.md")], key=lambda x: int(x.split("_part_")[1].split("_OCR.md")[0]))
    merged_content = ""

    # 각 마크다운 파일의 내용을 순서대로 병합
    for md_file in md_files:
        with open(os.path.join(dir_path, md_file), "r", encoding="utf-8") as f:
            merged_content += f.read() + "\n\n"

    # 병합된 내용을 최종 보고서 파일로 저장
    with open("final_report.md", "w", encoding="utf-8") as f:
        f.write(merged_content)

    # 임시 마크다운 파일과 디렉토리 삭제
    for md_file in md_files:
        os.remove(os.path.join(dir_path, md_file))
    os.rmdir(dir_path)


def ocr_model():
    # 임시 파일 생성
    file_name = upload_file()
    safe_file_name = "temp_upload_file.pdf"
    shutil.copy(file_name, safe_file_name)
    file_path = os.path.abspath(safe_file_name)

    try:
        # PDF 파일을 청크로 분할하고 각 청크의 시작 페이지 번호를 가져옴
        chunks, start_page_nums = split_pdf(file_path)

        # 각 청크를 병렬로 처리
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(chunks)) as executor:
            futures = [executor.submit(process_chunk, chunk, start_page_num) for chunk, start_page_num in zip(chunks, start_page_nums)]
            concurrent.futures.wait(futures)
    
    finally:
        # 임시 파일 삭제
        for chunk in chunks:
            if os.path.exists(chunk):
                os.remove(chunk)
        if os.path.exists(safe_file_name):
            os.remove(safe_file_name)

        # 병합된 마크다운 파일 생성
        merge_markdown_files()


def main():
    # 환경 변수 설정 및 UTF-8 인코딩 보장
    os.environ["PYTHONUTF8"] = "1"
    if sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    ocr_model()

    return


if __name__ == '__main__':
    main()