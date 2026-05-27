import os
import sys
import time
import queue
from tenacity import Retrying, wait_random_exponential, stop_after_delay, retry_if_exception
from google import genai
# from google.genai import types


class LLMCallManager:
    def __init__(self, max_requests_per_minute=14):
        self.client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))
        self.max_requests = max_requests_per_minute
        self.request_queue = queue.Queue()


    def acquire_slot(self):
        current_time = time.time()

        while self.request_queue[0] and current_time - self.request_queue[0] > 60:
            self.request_queue.get()

        if self.request_queue.qsize() >= self.max_requests:
            wait_time = current_time - self.request_queue[0]

            if wait_time > 0:
                time.sleep(wait_time)

            return self.acquire_slot()
        
        self.request_queue.put(time.time())


    @staticmethod
    def print_retry_message(retry_state):
        wait_time = retry_state.next_action.sleep
        attempt_num = retry_state.attempt_number
        exception = retry_state.outcome.exception()

        print(f"{wait_time}초 대기 후 재시도합니다. (누적 시도: {attempt_num}회) (사유: {exception})")


    @staticmethod
    def is_retryable_error(exception):
        error_str = str(exception).lower()
        return any(keyword in error_str for keyword in ["429", "503"])


    def call_llm_api(self, model, contents, config):
        self.acquire_slot()

        retryer = Retrying(
            wait=wait_random_exponential(multiplier=1, max=60),
            stop=stop_after_delay(1800),
            retry=retry_if_exception(self.is_retryable_error),
            before_sleep=self.print_retry_message
        )

        for attempt in retryer:
            with attempt:
                return self.client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )


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


# @retry(
#         wait=wait_random_exponential(multiplier=1, max=60),
#         stop=stop_after_delay(1800),
#         retry=retry_if_exception(is_retryable_error),
#         before_sleep=print_retry_message
# )
# def call_gemini_api(model, contents, schema):
#     client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))
#     return client.models.generate_content(
#         model=model,
#         contents=contents,
#         config=types.GenerateContentConfig(
#             response_mime_type="application/json",
#             response_schema=schema,
#             temperature=0.0
#         )
#     )