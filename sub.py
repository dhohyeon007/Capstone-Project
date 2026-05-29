import os
import sys
import time
import threading
from collections import deque
from tenacity import Retrying, wait_random_exponential, stop_after_delay, retry_if_exception
from google import genai
from pathlib import Path
# from google.genai import types


class LLMCallManager:
    def __init__(self, max_requests_per_minute=4):
        self.client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))
        self.model_list = [
            'gemini-3.5-flash',
            'gemini-3-flash-preview',
            'gemini-3.1-flash-lite',
            'gemini-2.5-flash',
            'gemini-2.5-flash-lite'
        ]
        self.current_model_idx = 0
        self.max_requests = max_requests_per_minute
        self.request_queue = deque()
        self.lock = threading.Lock()


    def acquire_slot(self):
        with self.lock:
            current_time = time.time()

            while self.request_queue and current_time - self.request_queue[0] > 60:
                self.request_queue.popleft()

            if len(self.request_queue) >= self.max_requests:
                wait_time = 60 - (current_time - self.request_queue[0])

                if wait_time > 0:
                    print(f"RPM Break: {wait_time}초 대기")
                    time.sleep(wait_time)

                self.request_queue.popleft()
            
            self.request_queue.append(time.time())


    def switch_model(self):
        if self.current_model_idx < len(self.model_list):
            self.current_model_idx += 1


    @staticmethod
    def print_retry_message(retry_state):
        wait_time = retry_state.next_action.sleep
        attempt_num = retry_state.attempt_number
        exception = retry_state.outcome.exception()

        print(f"{wait_time}초 대기 후 재시도합니다. (누적 시도: {attempt_num}회) (사유: {exception})")


    @staticmethod
    def is_retryable_error(exception):
        error_str = str(exception).lower()
        return any(keyword in error_str for keyword in ["503"])


    def call_llm_api(self, contents, config):
        while self.current_model_idx < len(self.model_list):
            self.acquire_slot()

            retryer = Retrying(
                wait=wait_random_exponential(multiplier=1, max=10),
                stop=stop_after_delay(1800),
                retry=retry_if_exception(self.is_retryable_error),
                before_sleep=self.print_retry_message,
                reraise=True
            )

            try:
                for attempt in retryer:
                    current_model = self.model_list[self.current_model_idx]
                    with attempt:
                        return self.client.models.generate_content(
                            model=current_model,
                            contents=contents,
                            config=config
                        )
                    
            except Exception as e:
                if "429" in str(e) or "RESOURCE EXHAUSTED" in str(e):
                    print(f"[{current_model}] 429 에러 발생 (일일 할당량 소진 판단).")

                    self.current_model_idx += 1

                    if self.current_model_idx >= len(self.model_list):
                        print("더 이상 사용할 수 있는 하위 모델이 없습니다. 작동을 종료합니다.")
                        exit_program()
                        sys.exit(1)

                    next_model = self.model_list[self.current_model_idx]
                    print(f"[{next_model}] 모델로 변경합니다.")
                    continue

                else:
                    print(f"에러 발생: {e}")
                    exit_program()
                    sys.exit(1)


def select_file():
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
            exit_program()
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


def start_program():
    parent_dir = Path("data")
    text_dir = parent_dir / "text"
    image_dir = parent_dir / "images"

    parent_dir.mkdir(exist_ok=True)
    text_dir.mkdir(exist_ok=True)
    image_dir.mkdir(exist_ok=True)

    return parent_dir, text_dir, image_dir


def exit_program():
    parent_dir = Path("data")
    text_dir = parent_dir / "text"
    image_dir = parent_dir / "images"

    for filepath in text_dir.iterdir():
        if filepath.is_file():
            filepath.unlink()
    text_dir.rmdir()

    for filepath in image_dir.iterdir():
        if filepath.is_file():
            filepath.unlink()
    image_dir.rmdir()

    parent_dir.rmdir()