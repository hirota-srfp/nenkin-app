# app.py
import streamlit as st
import os
import tempfile
from PIL import Image

from ocr_validator import extract_nenkin_json
from pension_calc import calculate_pension_simulation
from report_generator import generate_pension_report
from main import SAMPLE_JSON_SEIJI, SAMPLE_JSON_MASAMI

st.set_page_config(page_title="AI年金スピード診断｜ひろた社労士FPパートナーズ", layout="wide")

st.title("📱 AIねんきん定期便 スピード診断ツール")
st.write("ねんきん定期便の画像（またはPDF）をアップロードするだけで、60歳・65歳・70歳の受給額比較と損益分岐点レポートを自動生成します。")

# サーバー側（Secretsまたは環境変数）にAPIキーが設定されているか確認
server_api_key = None
try:
    if "GEMINI_API_KEY" in st.secrets:
        server_api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass
if not server_api_key:
    server_api_key = os.environ.get("GEMINI_API_KEY")

st.sidebar.header("⚙️ モード選択")
run_mode = st.sidebar.radio(
    "実行モードを選んでください",
    ["本番モード（画像をアップロード）", "デモモード（50歳以上様式）", "デモモード（50歳未満様式）"]
)

# サーバーにAPIキーが未設定の場合のみ、サイドバーに入力欄を表示する
if server_api_key:
    api_key = server_api_key
    st.sidebar.success("🔑 AIエンジン接続済み")
else:
    api_key = st.sidebar.text_input("Gemini APIキー（開発テスト用）", type="password")

uploaded_file = None
if run_mode == "本番モード（画像をアップロード）":
    st.info("💡 **撮影のポイント：** スマートフォンで撮影する場合は、ねんきん定期便の「老齢年金の見込額（棒グラフの面）」がはっきり写るように撮影してください。アップロードされた画像は解析後に即時自動削除されます。")
    uploaded_file = st.file_uploader("ねんきん定期便の画像（PNG/JPG/PDF）を選択", type=["png", "jpg", "jpeg", "pdf"])

st.markdown("---")

if st.button("🚀 診断レポートを生成する", type="primary"):
    if run_mode == "本番モード（画像をアップロード）" and not uploaded_file:
        st.warning("ねんきん定期便の画像またはPDFをアップロードしてください。")
    elif run_mode == "本番モード（画像をアップロード）" and not api_key:
        st.warning("左側のサイドバーにGemini APIキーを入力してください。")
    else:
        # ステップごとの進捗状況をリアルタイム表示して待ち時間の不安を解消する
        with st.status("⏳ AIスピード診断を開始しています...", expanded=True) as status:
            try:
                if run_mode == "デモモード（50歳以上様式）":
                    st.write("📄 サンプルデータ（50歳以上様式）を読み込んでいます...")
                    ocr_data = SAMPLE_JSON_SEIJI
                    label = "50歳以上様式・55歳時点モデル"
                elif run_mode == "デモモード（50歳未満様式）":
                    st.write("📄 サンプルデータ（50歳未満様式）を読み込んでいます...")
                    ocr_data = SAMPLE_JSON_MASAMI
                    label = "50歳未満様式・第3号継続推計モデル"
                else:
                    label = "AI読取・お客様データ"
                    st.write("📷 ステップ1/3：アップロードされた画像を最適化しています...")
                    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
                        tmp.write(uploaded_file.getvalue())
                        tmp_path = tmp.name

                    st.write("🤖 ステップ2/3：AIがねんきん定期便の数値を読み取っています（約5〜15秒）...")
                    ocr_data = extract_nenkin_json(tmp_path, api_key=api_key)
                    os.remove(tmp_path)  # 画像を即時削除

                st.write("📊 ステップ3/3：損益分岐点と元本回収ラインを計算し、グラフを描画しています...")
                calc_result = calculate_pension_simulation(ocr_data, label_name=label)

                output_filename = "app_report.png"
                generate_pension_report(calc_result, output_filename=output_filename)

                status.update(label="✅ 診断レポートが完成しました！", state="complete", expanded=False)

                image = Image.open(output_filename)
                st.image(image, use_container_width=True)

                with open(output_filename, "rb") as file:
                    st.download_button(
                        label="📥 レポート画像をスマホ/PCに保存する",
                        data=file,
                        file_name="nenkin_speed_diagnosis.png",
                        mime="image/png"
                    )

                with st.expander("🛠️ 裏側でAIが抽出したJSONデータを見る（確認用）"):
                    st.json(ocr_data)

            except Exception as e:
                status.update(label="❌ エラーが発生しました", state="error", expanded=True)
                st.error(f"エラー詳細: {e}")