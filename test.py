import os
from google import genai

# 1. 클라이언트 초기화 
# 환경 변수에 GEMINI_API_KEY가 설정되어 있다면 자동으로 인식합니다.
# 명시적으로 넣으려면 genai.Client(api_key="내_API_키") 형식으로 작성합니다.
client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))

print("🔍 최신 SDK 기준 사용 가능한 생성형 모델 목록")
print("=" * 50)

try:
    # 2. 클라이언트를 통해 전체 모델 목록 조회
    # 최신 SDK에서는 client.models.list() 메서드를 사용합니다.
    models = client.models.list()
    available_models = []
    
    for model in models:
        # 3. 텍스트 및 멀티모달 생성(generateContent)을 지원하는 모델만 필터링
        # 최신 모델 객체의 supported_generation_methods 속성을 검사합니다.
        if model.supported_actions and 'generateContent' in model.supported_actions:
            available_models.append(model.name)
            
            # 모델 이름에 따른 시각적 분류
            name_lower = model.name.lower()
            if 'pro' in name_lower:
                print(f"🚀 [Pro 모델]   {model.name}")
            elif 'flash' in name_lower:
                print(f"⚡ [Flash 모델] {model.name}")
            else:
                print(f"✅ [기타 모델]   {model.name}")
                
    print("=" * 50)
    print(f"총 {len(available_models)}개의 생성형 모델을 사용할 수 있습니다.")
    
    if not available_models:
        print("⚠️ 권한 내에서 사용 가능한 생성형 모델이 없습니다. API 키 설정을 확인해 주세요.")
        
except Exception as e:
    print(f"❌ 모델 목록을 불러오는 중 에러가 발생했습니다:\n{e}")