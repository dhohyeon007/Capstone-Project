from Capstone_project import upload_file
from google import genai
from google.genai import types
import json
import os
import pandas as pd


def main():
    # Google GenAI 클라이언트 초기화
    client = genai.Client(api_key=os.environ.get('GOOGLE_API_KEY'))

    # JSON 스키마 로드
    schema_path = "extraction_schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        loaded_schema = json.load(f)

    # 파일 경로 가져오기
    file_path = upload_file()
    
    # Google GenAI 모델을 사용하여 PDF에서 정보 추출
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=loaded_schema,
        temperature=0.1
    )
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[file_path, "제공된 JSON 스키마 구조에 맞게 문서의 정보를 정확히 추출하시오."],
        config=config
    )

    extracted_data = json.loads(response.text)
    output_path = os.path.abspath(os.path.join(os.getcwd(), "extracted_data.xlsx"))
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        df_main = pd.json_normalize(extracted_data)
        df_main.to_excel(writer, sheet_name='기본정보_및_통계', index=False)

        if "projects" in extracted_data and isinstance(extracted_data["projects"], list):
            df_projects = pd.DataFrame(extracted_data["projects"])

            for col in df_projects.columns:
                if df_projects[col].apply(type).eq(list).any() or df_projects[col].apply(type).eq(dict).any():
                    df_projects[col] = df_projects[col].astype(str)

            df_projects.to_excel(writer, sheet_name='세부사업목록', index=False)

        if "reduction_targets" in extracted_data and "sector_targets" in extracted_data["reduction_targets"]:
            df_sector_targets = pd.DataFrame(extracted_data["reduction_targets"]["sector_targets"])
            df_sector_targets.to_excel(writer, sheet_name='부문별_감축목표', index=False)


if __name__ == '__main__':
    main()