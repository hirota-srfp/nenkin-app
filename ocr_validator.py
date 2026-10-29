# ocr_validator.py
import os
import json
import fitz  # PyMuPDF
from PIL import Image
import io
from google import genai
from google.genai import types

PROMPT_NENKIN_OCR = """
あなたは社会保険労務士・FP業務を支援する高精度OCR・データ構造化AIです。
アップロードされた「ねんきん定期便」の画像から、以下のJSONスキーマに従って数値を正確に抽出してください。

【個人情報保護の絶対ルール】
氏名、住所、照会番号、アクセスキーなどの個人情報は一切抽出せず無視してください。

【抽出ルール】
1. 様式判定（format_type）:
   - 表面に「老齢年金の見込額（65歳・70歳・75歳）」が印字されていれば `"over_50"`（50歳以上様式）
   - 表面に「これまでの加入実績に応じた年金額（昨年・今年）」が印字されていれば `"under_50"`（50歳未満様式）
2. 年齢（record_age）:
   - 表面の棒グラフの下にある「（〇〇歳時点）」の数字（例: 55）を抽出してください。書かれていない場合は null にしてください。
3. 最近の月別状況（直近の加入区分・報酬）:
   - 表の一番下（直近月）の加入区分が「厚年」なら `"kousei"`、「1号」なら `"kyoshutsu_1"`、「3号納付」なら `"hihuyou_3"` と判定してください。
   - 「厚年」の場合、一番下の月（直近月）の「標準報酬月額（千円）」と「保険料納付額（円）」を抽出してください。
   - 過去1年間（直近12ヶ月分）の「標準賞与額（千円）」の合計を算出してください（例：1,500千円が2回あれば 3000）。
4. 裏面（2ページ目）の情報がある場合:
   - 「2. これまでの年金加入期間」の「年金加入期間合計（a+b+c）」の月数
   - 「3. 老齢年金の種類と見込額（または加入実績に応じた年金額）」の「老齢基礎年金（円）」「老齢厚生年金合計（円）」を抽出してください。

必ず以下のJSONフォーマットのみを出力してください：
{
  "validation": {
    "is_nenkin_teikibin": true,
    "is_readable": true,
    "format_type": "over_50 または under_50",
    "error_message": null
  },
  "extracted_data": {
    "issue_year": "令和7年度",
    "record_age": 55,
    "current_category": "kousei または kyoshutsu_1 または hihuyou_3",
    "latest_std_monthly_salary_thousand": 650,
    "latest_monthly_premium_yen": 59475,
    "annual_std_bonus_thousand": 3000,
    "cumulative_paid_total_yen": 18058786,
    "total_enrolled_months": 411,
    "pension_65_total_yen": 2338381,
    "pension_70_total_yen": 3320501,
    "pension_75_total_yen": 4302621,
    "current_achieved_pension_total_yen": null,
    "basic_pension_yen": 793580,
    "welfare_pension_yen": 1544801
  }
}
"""

# 一度成功したモデル名を記憶して2回目以降を高速化するキャッシュ変数
_CACHED_MODEL_NAME = None

def load_file_as_images(file_path: str) -> list:
    """PDFまたは画像ファイルを高速処理向けに最適化したPIL Imageリストに変換する"""
    ext = os.path.splitext(file_path)[1].lower()
    images = []
    if ext == ".pdf":
        doc = fitz.open(file_path)
        # 最大2ページ（表面・裏面）までに制限し、dpi=120で高速化
        for page_index in range(min(2, len(doc))):
            page = doc[page_index]
            pix = page.get_pixmap(dpi=120)
            img = Image.open(io.BytesIO(pix.tobytes("jpeg")))
            images.append(img)
        doc.close()
    else:
        img = Image.open(file_path)
        img.thumbnail((1600, 1600))  # スマホの巨大写真を適度なサイズに縮小して高速化
        images.append(img)
    return images

def get_fast_gemini_model(client) -> str:
    """利用可能なモデル一覧から最も高速なFlash系モデルを自動選択する"""
    global _CACHED_MODEL_NAME
    if _CACHED_MODEL_NAME:
        return _CACHED_MODEL_NAME

    try:
        models = []
        for m in client.models.list():
            name = getattr(m, "name", "")
            actions = getattr(m, "supported_actions", None) or getattr(m, "supported_generation_methods", None)
            if actions and "generateContent" not in actions:
                continue
            low = name.lower()
            if "gemini" in low and "embedding" not in low and "imagen" not in low and "tts" not in low:
                models.append(name)

        # 高速な flash モデルを最優先で選択（proは長考して遅くなるため後回し）
        for keyword in ["flash-lite", "flash", "gemini"]:
            for m_name in models:
                if keyword in m_name.lower() and "pro" not in m_name.lower():
                    _CACHED_MODEL_NAME = m_name
                    return m_name
        if models:
            _CACHED_MODEL_NAME = models[0]
            return models[0]
    except Exception:
        pass
    return "gemini-2.5-flash"

def extract_nenkin_json(file_path: str, api_key: str = None) -> dict:
    """ねんきん定期便のファイルからAIでJSONデータを高速抽出する"""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("GEMINI_API_KEY が設定されていません。")

    client = genai.Client(api_key=key.strip())
    images = load_file_as_images(file_path)
    contents = images + [PROMPT_NENKIN_OCR]

    model_name = get_fast_gemini_model(client)
    print(f"使用AIモデル: {model_name}")

    # Thinking（長考モード）が使えるモデルの場合はオフにして数秒で回答させる設定を試みる
    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )
    except Exception:
        # thinking_config非対応モデルの場合は通常設定で実行
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.0,
        )
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

    result_dict = json.loads(response.text)
    return result_dict