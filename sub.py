import os
import sys
import logging

from functools import wraps
from collections import deque
import threading
import time
import random

from google import genai
# from google.genai import types

from pathlib import Path


logger = logging.getLogger(__name__)
logging.basicConfig(filename="sub.log", level=logging.WARNING)


def retry_with_backoff(max_duration=300, base_delay=1, max_delay=10):
    """최대 허용 시간(5분) 내에서 지수 백오프로 재시도하는 데코레이터"""
    def deco(func):
        @wraps
        def wrapper(*args, **kwargs):
            start_time = time.time()
            retries = 0
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e)

                if "429" in error_str:
                    raise e
                
                if not any(code in error_str for code in ["500", "502", "503", "504"]):
                    raise e
                
                elapsed_time = time.time() - start_time
                if elapsed_time >= max_duration:
                    logger.error("최대 허용 시간 초과.")
                    raise e
                
                retries += 1
                jitter = random.uniform(-0.2, 0.2)
                exp_delay = base_delay * (2 ** (retries - 1))
                wait_time = min((exp_delay + jitter), max_delay)

                remining_time = max_duration - elapsed_time
                if wait_time > remining_time:
                    wait_time = remining_time

                logger.warning(f"{wait_time:.2f}초 대기 후 재시도합니다. (누적 시도: {retries + 1}회) (사유: {e})")
                time.sleep(wait_time)

            return wrapper
        return deco


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
        """RPM 제한 방어 코드"""
        with self.lock:
            current_time = time.time()

            while self.request_queue and current_time - self.request_queue[0] > 60:
                self.request_queue.popleft()

            if len(self.request_queue) >= self.max_requests:
                wait_time = 60 - (current_time - self.request_queue[0])

                if wait_time > 0:
                    logger.warning(f"RPM Break: {wait_time}초 대기")
                    time.sleep(wait_time)

                self.request_queue.popleft()
            
            self.request_queue.append(time.time())


    @retry_with_backoff(
            max_duration=300,
            base_delay=1,
            max_delay=10
    )
    def execute_api_call(self, current_model, contents, config):
        """실제 API 호출하는 내부 메서드(재시도 로직 적용)"""
        return self.client.models.generate_content(
            model=current_model,
            contents=contents,
            config=config
        )


    def call_llm_api(self, contents, config):
        """외부에서 호출하는 메서드(모델 스위칭 담당)"""
        while self.current_model_idx < len(self.model_list):
            current_model = self.model_list[self.current_model_idx]
            self.acquire_slot()

            try:
                return self.execute_api_call(current_model, contents, config)                
                    
            except Exception as e:
                if "429" in str(e) or "RESOURCE EXHAUSTED" in str(e).upper():
                    logger.warning(f"[{current_model}] 429 에러 발생 (일일 할당량 소진 판단).")

                    self.current_model_idx += 1
                    if self.current_model_idx >= len(self.model_list):
                        logger.error("더 이상 사용할 수 있는 하위 모델이 없습니다. 종료합니다.")
                        epilogue()
                        raise e

                    next_model = self.model_list[self.current_model_idx]
                    logger.warning(f"[{next_model}] 모델로 변경합니다.")
                    continue

                else:
                    logger.error(f"에러 발생: {e}")
                    epilogue()
                    raise e


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
            epilogue()
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


def prologue():
    """임시 파일 저장 디렉토리 생성"""
    parent_dir = Path("data")
    text_dir = parent_dir / "text"
    image_dir = parent_dir / "images"
    json_dir = parent_dir / "json"

    parent_dir.mkdir(exist_ok=True)
    text_dir.mkdir(exist_ok=True)
    image_dir.mkdir(exist_ok=True)
    json_dir.mkdir(exist_ok=True)

    return text_dir, image_dir, json_dir


def epilogue():
    """임시 파일 및 디렉토리 삭제"""
    parent_dir = Path("data")
    text_dir = parent_dir / "text"
    image_dir = parent_dir / "images"
    json_dir = parent_dir / "json"

    for filepath in text_dir.iterdir():
        if filepath.is_file():
            filepath.unlink()
    text_dir.rmdir()

    for filepath in image_dir.iterdir():
        if filepath.is_file():
            filepath.unlink()
    image_dir.rmdir()

    # for filepath in json_dir.iterdir():
    #     if filepath.is_file():
    #         filepath.unlink()
    # json_dir.rmdir()

    # parent_dir.rmdir()