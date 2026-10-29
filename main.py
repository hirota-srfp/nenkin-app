# main.py
import os
import json
from ocr_validator import extract_nenkin_json
from pension_calc import calculate_pension_simulation
from report_generator import generate_pension_report

# ---------------------------------------------------------
# テスト用サンプルデータ（添付のねんきん定期便2名分から抽出したJSON）
# ---------------------------------------------------------
SAMPLE_JSON_SEIJI = {
    "validation": {"is_nenkin_teikibin": True, "is_readable": True, "format_type": "over_50", "error_message": None},
    "extracted_data": {
        "issue_year": "令和7年度",
        "record_age": 55,
        "current_category": "kousei",
        "latest_std_monthly_salary_thousand": 650,
        "latest_monthly_premium_yen": 59475,
        "annual_std_bonus_thousand": 3000,
        "cumulative_paid_total_yen": 18058786,
        "total_enrolled_months": 411,
        "pension_65_total_yen": 2338381,
        "pension_70_total_yen": 3320501,
        "pension_75_total_yen": 4302621,
        "current_achieved_pension_total_yen": None,
        "basic_pension_yen": 793580,
        "welfare_pension_yen": 1544801
    }
}

SAMPLE_JSON_MASAMI = {
    "validation": {"is_nenkin_teikibin": True, "is_readable": True, "format_type": "under_50", "error_message": None},
    "extracted_data": {
        "issue_year": "令和7年度",
        "record_age": 49,
        "current_category": "hihuyou_3",
        "latest_std_monthly_salary_thousand": None,
        "latest_monthly_premium_yen": 0,
        "annual_std_bonus_thousand": 0,
        "cumulative_paid_total_yen": 2271672,
        "total_enrolled_months": 334,
        "pension_65_total_yen": None,
        "pension_70_total_yen": None,
        "pension_75_total_yen": None,
        "current_achieved_pension_total_yen": 729706,
        "basic_pension_yen": 578725,
        "welfare_pension_yen": 150981
    }
}

def run_pipeline(file_path: str = None, demo_json: dict = None, label_name: str = "診断モデル", output_prefix: str = "output"):
    """
    モジュール②(OCR) → モジュール③(計算) → モジュール④(レポート出力) を一気通貫で実行する
    """
    # 1. データの取得（ファイル指定時はAI OCR実行、未指定時はデモJSONを使用）
    if file_path and os.path.exists(file_path):
        print(f"[{label_name}] AIでファイルを読み取っています: {file_path}")
        ocr_data = extract_nenkin_json(file_path)
    else:
        print(f"[{label_name}] 内蔵の抽出済みJSONデータで処理を実行します...")
        ocr_data = demo_json

    # 抽出されたJSONを保存（確認・再利用用）
    json_filename = f"{output_prefix}_extracted.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(ocr_data, f, ensure_ascii=False, indent=2)
    print(f" -> JSONデータを保存しました: {json_filename}")

    # 2. 計算エンジンでシミュレーション実行
    calc_result = calculate_pension_simulation(ocr_data, label_name=label_name)

    # 3. グラフ＆診断レポート画像の出力
    image_filename = f"{output_prefix}_report.png"
    generate_pension_report(calc_result, output_filename=image_filename)

if __name__ == "__main__":
    # ★まずはAPIキーなしでそのまま実行し、2名分のJSONとグラフ画像が出力されることを確認できます！
    run_pipeline(demo_json=SAMPLE_JSON_SEIJI, label_name="50歳以上様式・55歳時点モデル", output_prefix="seiji")
    run_pipeline(demo_json=SAMPLE_JSON_MASAMI, label_name="50歳未満様式・第3号継続推計モデル", output_prefix="masami")

    # ★実際のPDFやスマホ撮影画像をAIで読み込ませる場合は、環境変数 GEMINI_API_KEY を設定して以下を有効化してください：
    # os.environ["GEMINI_API_KEY"] = "あなたのAPIキー"
    # run_pipeline(file_path="ねんきん定期便(成).pdf", label_name="本人様", output_prefix="real_test")