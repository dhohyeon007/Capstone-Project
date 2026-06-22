import os
import time
import json
import random
import threading
import logging
import re
from util import setup_environment
from collections import deque
from functools import wraps
from google import genai


setup_environment()


logger = logging.getLogger(__name__)


def retry_with_backoff(max_duration=300, base_delay=1, max_delay=10):
    """최대 허용 시간(5분) 내에서 지수 백오프로 재시도하는 데코레이터"""
    def deco(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            retries = 0

            while True:
                try:
                    return func(*args, **kwargs)
                
                except Exception as e:
                    error_str = str(e)

                    if "429" in error_str or "RESOURCE EXHAUSTED" in error_str:
                        is_rpd_limit = False

                        try:
                            json_start_idx = error_str.find('{')
                            if json_start_idx != -1:
                                error_str_json = error_str[json_start_idx:]
                                error_dict = json.loads(error_str_json.replace("'", '"'))

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
                            
                        except Exception as parse_error:
                            logger.debug(f"429 에러 JSON 파싱 실패: {parse_error}")

                        error_str_lower = error_str.lower()
                        if not is_rpd_limit and ("perday" in error_str_lower or "per day" in error_str_lower):
                            is_rpd_limit = True

                        if is_rpd_limit:
                            raise e
                        else:
                            pass
                    
                    elif not any(code in error_str for code in ["500", "502", "503", "504"]):
                        raise e
                    
                    elapsed_time = time.time() - start_time
                    if elapsed_time >= max_duration:
                        logger.error("최대 허용 시간 초과.")
                        raise e
                    
                    retries += 1
                    jitter = random.uniform(-0.2, 0.2)
                    exp_delay = base_delay * (2 ** (retries - 1))
                    wait_time = min((exp_delay + jitter), max_delay)

                    remaining_time = max_duration - elapsed_time
                    if wait_time > remaining_time:
                        wait_time = remaining_time

                    logger.warning(f"{wait_time:.2f}초 대기 후 재시도합니다. (사유: {e})")
                    time.sleep(wait_time)

        return wrapper
    return deco


class LLMCallManager:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))
        self.model_list = [
            {'name': 'gemini-3.5-flash', 'rpm': 5},
            {'name': 'gemini-3-flash-preview', 'rpm': 5},
            {'name': 'gemini-3.1-flash-lite', 'rpm': 15},
            {'name': 'gemini-2.5-flash', 'rpm': 5},
            {'name': 'gemini-2.5-flash-lite', 'rpm': 10},
        ]
        self.current_model_idx = 0
        self.max_requests = self.model_list[self.current_model_idx]['rpm']
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
                    logger.warning(f"RPM Break: {wait_time:.2f}초 대기")
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
        while True:
            self.acquire_slot()

            with self.lock:
                if self.current_model_idx >= len(self.model_list):
                    raise RuntimeError("모든 모델 소진됨")
                
                current_model = self.model_list[self.current_model_idx]['name']
                attempted_idx = self.current_model_idx

            try:
                return self.execute_api_call(current_model, contents, config)                
                    
            except Exception as e:
                if "429" in str(e) or "RESOURCE EXHAUSTED" in str(e).upper():
                    with self.lock:
                        if self.current_model_idx == attempted_idx:
                            logger.warning(f"[{current_model}] 일일 할당량 소진")
                            self.current_model_idx += 1

                            if self.current_model_idx >= len(self.model_list):
                                logger.error("더 이상 사용할 수 있는 하위 모델이 없습니다. 종료합니다.")
                                raise RuntimeError("모든 모델 소진됨")

                            next_model = self.model_list[self.current_model_idx]['name']
                            self.max_requests = self.model_list[self.current_model_idx]['rpm']
                            self.request_queue.clear()
                            logger.warning(f"[{next_model}] 모델로 변경합니다.")
                        else:
                            pass

                    continue

                else:
                    logger.error(f"에러 발생: {e}")
                    raise e
