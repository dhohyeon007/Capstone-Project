Google Generative AI(GenAI)를 Python으로 사용하기 위한 공식 라이브러리인 `google-generative-ai`를 기준으로 자주 사용되는 객체(Objects)와 메소드(Methods)를 설명해 드리겠습니다.

Gemini 모델을 중심으로 설명하며, 기본적인 텍스트 생성부터 멀티모달, 채팅 세션까지 다룹니다.

---

### 1. 기본 설정 및 초기화 (Setup & Configuration)

가장 먼저 해야 할 일은 API 키를 설정하고 라이브러리를 초기화하는 것입니다.

- **메소드:** `genai.configure()`
  - **설명:** Google GenAI API 키를 설정하여 라이브러리가 API 서버와 통신할 수 있도록 합니다. 보통 스크립트 시작 부분에 한 번 호출합니다.
  - **예시:**

    ```python
    import google.generativeai as genai
    import os

    # API 키는 환경 변수로 관리하는 것이 좋습니다.
    # genai.configure(api_key="YOUR_API_KEY")  # 직접 입력하는 경우
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    ```

### 2. 모델 객체 (Model Object)

GenAI 모델과 상호작용하기 위한 핵심 객체입니다.

- **객체:** `genai.GenerativeModel`
  - **설명:** 특정 GenAI 모델(예: `gemini-pro`, `gemini-pro-vision`)을 로드하고 인스턴스화하는 데 사용됩니다. 이 객체를 통해 텍스트 생성, 채팅, 멀티모달 입력 처리 등의 메소드를 호출합니다.
  - **주요 매개변수:**
    - `model_name`: 사용할 모델의 이름 (예: `'gemini-pro'`, `'gemini-pro-vision'`).
    - `generation_config`: 생성 설정 (온도, 최대 토큰 등)을 지정합니다.
    - `safety_settings`: 안전 필터링 설정을 지정합니다.
  - **예시:**

    ```python
    # 텍스트 전용 모델
    model = genai.GenerativeModel('gemini-pro')

    # 멀티모달 (텍스트 + 이미지) 모델
    vision_model = genai.GenerativeModel('gemini-pro-vision')
    ```

### 3. 콘텐츠 생성 메소드 (Content Generation Methods)

실제로 모델에게 요청을 보내 응답을 받는 핵심 메소드입니다.

- **메소드:** `model.generate_content()`
  - **설명:** 모델에 프롬프트를 보내 콘텐츠를 생성합니다. 텍스트, 이미지, 오디오 등 다양한 형태의 입력을 처리할 수 있는 가장 범용적인 메소드입니다. 스트리밍 응답도 지원합니다.
  - **주요 매개변수:**
    - `contents`: 모델에 전달할 프롬프트. 문자열, `PIL.Image.Image` 객체, 또는 이들의 리스트가 될 수 있습니다.
    - `generation_config`: (선택 사항) 해당 요청에만 적용될 생성 설정을 지정합니다.
    - `safety_settings`: (선택 사항) 해당 요청에만 적용될 안전 필터링 설정을 지정합니다.
    - `stream`: (선택 사항) `True`로 설정하면 응답을 스트리밍 방식으로 받습니다.
  - **예시 (텍스트):**
    ```python
    response = model.generate_content("세계에서 가장 높은 산은 무엇인가요?")
    print(response.text)
    ```
  - **예시 (멀티모달 - 텍스트 + 이미지):**

    ```python
    from PIL import Image
    import requests
    from io import BytesIO

    # 이미지 URL에서 이미지 로드 (예시)
    image_url = "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png"
    response_image = requests.get(image_url)
    img = Image.open(BytesIO(response_image.content))

    vision_model = genai.GenerativeModel('gemini-pro-vision')
    response_vision = vision_model.generate_content(["이 이미지에 대해 설명해주세요.", img])
    print(response_vision.text)
    ```

  - **예시 (스트리밍):**
    ```python
    response_stream = model.generate_content("인공지능에 대해 간략히 설명해주세요.", stream=True)
    for chunk in response_stream:
        print(chunk.text, end='')
    print()
    ```

### 4. 채팅 세션 객체 및 메소드 (Chat Session Object & Methods)

대화형 애플리케이션을 만들 때 유용하며, 이전 대화 내용을 기억하는 세션 기반의 상호작용을 제공합니다.

- **메소드:** `model.start_chat()`
  - **설명:** 새로운 채팅 세션을 시작하고 `ChatSession` 객체를 반환합니다.
  - **주요 매개변수:**
    - `history`: (선택 사항) 기존 대화 기록을 미리 로드하여 세션을 시작할 수 있습니다.
  - **객체:** `ChatSession`
    - **설명:** `start_chat()` 메소드에 의해 생성되는 객체로, 대화의 상태(history)를 관리하고 메시지를 주고받는 데 사용됩니다.
    - **속성:**
      - `history`: 현재까지의 대화 기록(메시지 리스트)을 담고 있습니다.
    - **메소드:** `chat.send_message()`
      - **설명:** 채팅 세션에 메시지를 보내고 모델의 응답을 받습니다. `generate_content()`와 유사하지만, `ChatSession`의 `history`에 자동으로 대화가 추가됩니다.
      - **주요 매개변수:**
        - `prompt`: 모델에 전달할 메시지.
        - `stream`: (선택 사항) `True`로 설정하면 스트리밍 응답을 받습니다.
  - **예시:**

    ```python
    chat = model.start_chat(history=[]) # 빈 기록으로 시작

    response1 = chat.send_message("안녕하세요! 저는 당신과 대화하고 싶습니다.")
    print(f"모델: {response1.text}")

    response2 = chat.send_message("제가 방금 뭐라고 말했죠?")
    print(f"모델: {response2.text}")

    # 대화 기록 확인
    for message in chat.history:
        print(f"{message.role}: {message.parts[0].text}")
    ```

### 5. 응답 객체 (Response Objects)

`generate_content()`나 `send_message()` 호출 시 반환되는 객체입니다.

- **객체:** `GenerateContentResponse` (또는 `ChatResponse` - 사실상 동일)
  - **설명:** 모델의 응답을 담고 있는 객체입니다. 생성된 텍스트, 안전 필터링 정보, 프롬프트 피드백 등을 포함합니다.
  - **주요 속성:**
    - `text`: (가장 자주 사용됨) 모델이 생성한 텍스트 콘텐츠입니다.
    - `candidates`: 모델이 제안한 여러 개의 응답 후보 리스트입니다. (일반적으로 하나만 사용)
      - 각 `Candidate` 객체는 `content` 속성을 가집니다.
      - `content`: 모델이 생성한 실제 콘텐츠를 담고 있는 `Content` 객체입니다.
        - `parts`: `Content`는 여러 부분(`Part` 객체)으로 구성될 수 있습니다. 텍스트는 `Part` 객체의 `text` 속성에 있습니다. `response.text`는 이 과정을 간소화한 것입니다.
    - `prompt_feedback`: 프롬프트에 대한 피드백(예: 안전 필터링으로 인해 프롬프트가 차단되었는지 여부)을 제공합니다.
      - `block_reason`: 프롬프트가 차단된 경우 그 이유.
      - `safety_ratings`: 프롬프트의 안전 등급.
    - `finish_reason`: 모델이 응답 생성을 중단한 이유 (예: `STOP`, `MAX_TOKENS`, `SAFETY`).
  - **예시:**

    ```python
    response = model.generate_content("짧은 시를 써주세요.")
    print(f"생성된 텍스트: {response.text}")

    if response.prompt_feedback:
        print(f"프롬프트 피드백: {response.prompt_feedback.block_reason}")
        for rating in response.prompt_feedback.safety_ratings:
            print(f"  {rating.category}: {rating.probability}")

    if response.candidates:
        print(f"종료 이유: {response.candidates[0].finish_reason}")
    ```

### 6. 유틸리티 및 설정 객체 (Utility & Configuration Objects)

모델의 동작을 세밀하게 제어하거나 특정 정보를 얻을 때 사용합니다.

- **객체:** `genai.GenerationConfig`
  - **설명:** 텍스트 생성의 파라미터(온도, 최대 토큰 등)를 정의하는 객체입니다. `GenerativeModel` 초기화 시 또는 `generate_content()` 호출 시 전달할 수 있습니다.
  - **주요 속성:**
    - `temperature`: 텍스트의 무작위성(창의성)을 조절합니다 (0.0 ~ 1.0).
    - `max_output_tokens`: 생성할 최대 토큰 수.
    - `top_p`: 확률이 높은 토큰부터 누적 확률이 `top_p`를 넘을 때까지의 토큰 중에서 샘플링합니다.
    - `top_k`: 확률이 높은 상위 `k`개의 토큰 중에서 샘플링합니다.
  - **예시:**
    ```python
    my_config = genai.GenerationConfig(
        temperature=0.9,
        max_output_tokens=100,
        top_p=0.8,
        top_k=40
    )
    response = model.generate_content("로맨틱 코미디 영화 줄거리 아이디어", generation_config=my_config)
    print(response.text)
    ```

- **객체:** `genai.SafetySetting`
  - **설명:** 특정 유해성 카테고리(`HarmCategory`)에 대한 차단 임계값(`HarmBlockThreshold`)을 설정하는 객체입니다.
  - **객체:** `genai.HarmCategory`
    - **설명:** 유해성 콘텐츠의 카테고리(예: `HARM_CATEGORY_HARASSMENT`, `HARM_CATEGORY_HATE_SPEECH`).
  - **객체:** `genai.HarmBlockThreshold`
    - **설명:** 특정 카테고리의 콘텐츠를 차단할 임계값(예: `BLOCK_NONE`, `BLOCK_LOW_AND_ABOVE`).
  - **예시:**
    ```python
    my_safety_settings = [
        genai.SafetySetting(
            category=genai.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=genai.HarmBlockThreshold.BLOCK_NONE # 증오 발언을 차단하지 않음 (주의해서 사용)
        ),
        genai.SafetySetting(
            category=genai.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=genai.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
        ),
    ]
    response = model.generate_content("논란의 여지가 있는 주제에 대한 의견", safety_settings=my_safety_settings)
    print(response.text)
    ```

- **메소드:** `model.count_tokens()`
  - **설명:** 주어진 콘텐츠(프롬프트)에 포함된 토큰 수를 계산합니다. API 호출 비용 예측 등에 유용합니다.
  - **예시:**
    ```python
    token_count = model.count_tokens("이 문장의 토큰 수를 세어주세요.")
    print(f"토큰 수: {token_count.total_tokens}")
    ```

---

이러한 객체와 메소드들은 Google GenAI 라이브러리를 사용하여 Gemini 모델과 효과적으로 상호작용하는 데 필수적입니다. 대부분의 사용 시나리오에서 위에 설명된 내용만으로 충분히 복잡한 애플리케이션을 구축할 수 있습니다.
