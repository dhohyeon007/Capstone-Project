from google import genai
from google.genai import types
from google.genai.errors import APIError
from dotenv import load_dotenv
from collections import deque
import os
import sys
import json
import threading
import time
import logging


logger = logging.getLogger(__name__)


class LLMCaller:
    def __init__(self):
        # Read-Only
        self.http_options = types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                initial_delay=1.0,
                max_delay=10.0,
                exp_base=2.0,
                jitter=0.2
            ),
            timeout=300000
        )
        load_dotenv()
        self.model_list = [
            {'name':'gemini-3.5-flash', 'rpm':5},
            {'name':'gemini-3-flash-preview', 'rpm':5},
            {'name':'gemini-3.1-flash-lite', 'rpm':15},
        ]
        

        # Read/Write
        self.api_key_idx = 1
        self.api_key = os.getenv(f"GEMINI_API_KEY_{self.api_key_idx}")
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=self.http_options
        )
        self.current_model_idx = 0
        self.request_queue = deque()

        # Lock
        self.lock = threading.Lock()


    def acquire_slot(self):
        """RPM 으로 인한 일일 할당량 사용 방지"""
        while True:
            wait_time = 0

            with self.lock:
                current_time = time.time()

                while current_time - self.request_queue[0] > 60:
                    self.request_queue.popleft()

                max_requests = self.model_list[self.current_model_idx]['rpm']

                if len(self.request_queue) >= max_requests:
                    wait_time = 60 - (current_time - self.request_queue[0])
                else:
                    self.request_queue.append(current_time)
                    return

            if wait_time > 0:
                logger.warning(f"RPM Break: Wait {wait_time:.2f} seconds...")
                time.sleep(wait_time)


    def parse_429_error_msg(self, error_str):
        """429 에러 메시지를 파싱하여 RPD 제한 여부를 반환"""
        is_rpd_limit = False

        try:
            json_start_idx = error_str.find('{')
            if json_start_idx != -1:
                error_json = error_str[json_start_idx:]
                error_dict = json.loads(error_json.replace("'", '"'))

                details = error_dict.get('error', {}).get('details', [])
                for detail in details:
                    violations = detail.get('violations', [])
                    for violation in violations:
                        quota_id = violation.get('quotaId', '').lower()

                        if 'perday' in quota_id:
                            is_rpd_limit = True
                            break

                    if is_rpd_limit:
                        break

        except Exception as e:
            logger.debug(f"Failed to parse 429 error JSON: {e}")

        return is_rpd_limit

    
    def switch_model(self):
        with self.lock:
            self.current_model_idx += 1

            if self.current_model_idx >= len(self.model_list):
                logger.warning("Models exhausted. Changing API key...")
                self.switch_api_key()
            
            self.request_queue.clear()


    def switch_api_key(self):
        """switch_model에서 lock 보유한 채로 실행"""
        self.api_key_idx += 1
        self.api_key = os.getenv(f"GEMINI_API_KEY_{self.api_key_idx}")
        if self.api_key is None:
            logger.error("API key exhausted. Terminating program.")
            sys.exit(1)
        else:
            self.client = genai.Client(
                api_key=self.api_key,
                http_options=self.http_options
            )
            self.current_model_idx = 0


    def call_llm(self, contents, config):
        while True:
            self.acquire_slot()

            with self.lock:
                current_model_name = self.model_list[self.current_model_idx]['name']
                attempted_model_idx = self.current_model_idx

            try:
                return self.client.models.generate_content(
                    model=current_model_name,
                    contents=contents,
                    config=config
                )
            
            except APIError as e:
                if e.code == 429:
                    is_rpd_limit = self.parse_429_error_msg(str(e))
                    # attempted_model_idx 확인을 통해 여러 스레드가 동시에 에러를 받았을 때 중복 스위칭 방지
                    if is_rpd_limit and self.current_model_idx == attempted_model_idx:
                        logger.warning("[RPD Limit] Resource exhausted. Changing model...")
                        self.switch_model()
                    else:
                        # RPD가 아닌 RPM, TPM 한도 초과라면 다시 루프를 돌아 acquire_slot에서 대기
                        pass

                elif e.code in (500, 502, 503, 504):
                    # 일시적인 서버 에러는 재시도
                    continue

                else:
                    logger.error(f"Error occured while calling LLM: {str(e)}")
                    sys.exit(1)