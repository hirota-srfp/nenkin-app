# pension_calc.py
import numpy as np

FULL_BASIC_PENSION_YEN = 831700       # 老齢基礎年金の満額（年額）
NATIONAL_PENSION_MONTHLY_YEN = 17510  # 国民年金保険料（月額目安）
WELFARE_PENSION_HALF_RATE = 0.0915    # 厚生年金保険料率（本人負担分 9.15%）
WELFARE_ACCRUAL_COEFF = 0.005481      # 厚生年金（報酬比例部分）乗率（5.481/1000）

def calculate_pension_simulation(ocr_json: dict, label_name: str = "診断モデル") -> dict:
    val = ocr_json.get("validation", {})
    if not val.get("is_nenkin_teikibin", False) or not val.get("is_readable", False):
        raise ValueError(f"読み取りエラー: {val.get('error_message', 'ねんきん定期便として認識できませんでした')}")

    ext = ocr_json["extracted_data"]
    fmt = val.get("format_type", "over_50")
    category = ext.get("current_category", "kousei")

    # 1. 60歳までの残り月数・年数の算出（年齢がnullの場合は加入月数から推定）
    record_age = ext.get("record_age")
    enrolled_months = ext.get("total_enrolled_months")
    if record_age is not None and record_age < 60:
        remaining_months = (60 - int(record_age)) * 12
        age_label = f"{int(record_age)}歳時点"
    elif enrolled_months is not None:
        remaining_months = max(0, 480 - int(enrolled_months))
        est_age = 20 + int(enrolled_months) // 12
        age_label = f"推計{est_age}歳時点"
    else:
        remaining_months = 60
        age_label = "現時点"
    remaining_years = remaining_months / 12.0

    # 2. 60歳までの追加納付予想額 ＆ 納付累計予想額の算出
    paid_current = int(ext.get("cumulative_paid_total_yen") or 0)
    if category == "kousei":
        monthly_salary_yen = (ext.get("latest_std_monthly_salary_thousand") or 0) * 1000
        monthly_prem = ext.get("latest_monthly_premium_yen") or int(round(monthly_salary_yen * WELFARE_PENSION_HALF_RATE))
        annual_bonus_yen = (ext.get("annual_std_bonus_thousand") or 0) * 1000
        bonus_prem_annual = int(round(annual_bonus_yen * WELFARE_PENSION_HALF_RATE))
        annual_prem = monthly_prem * 12 + bonus_prem_annual
        paid_future = int(round(annual_prem * remaining_years))
    elif category == "kyoshutsu_1":
        annual_prem = NATIONAL_PENSION_MONTHLY_YEN * 12
        paid_future = int(round(NATIONAL_PENSION_MONTHLY_YEN * remaining_months))
    else:
        annual_prem = 0
        paid_future = 0

    paid_projected = paid_current + paid_future

    # 3. 65歳・70歳・75歳・60歳受給額の算出
    if fmt == "over_50":
        amt_65 = int(ext["pension_65_total_yen"])
        amt_70 = int(ext.get("pension_70_total_yen") or round(amt_65 * 1.42))
        amt_75 = int(ext.get("pension_75_total_yen") or round(amt_65 * 1.84))
        amt_60 = int(round(amt_65 * 0.76))
    else:
        achieved_basic = int(ext.get("basic_pension_yen") or 0)
        achieved_welfare = int(ext.get("welfare_pension_yen") or 0)
        if enrolled_months:
            projected_months = min(480, int(enrolled_months) + remaining_months)
            projected_basic = int(round(FULL_BASIC_PENSION_YEN * (projected_months / 480.0)))
        else:
            projected_basic = FULL_BASIC_PENSION_YEN

        if category == "kousei":
            total_annual_remuneration = ((ext.get("latest_std_monthly_salary_thousand") or 0) * 12 + (ext.get("annual_std_bonus_thousand") or 0)) * 1000
            avg_monthly_remuneration = total_annual_remuneration / 12.0
            future_welfare_add = int(round(avg_monthly_remuneration * WELFARE_ACCRUAL_COEFF * remaining_months))
            projected_welfare = achieved_welfare + future_welfare_add
        else:
            projected_welfare = achieved_welfare

        amt_65 = projected_basic + projected_welfare
        amt_60 = int(round(amt_65 * 0.76))
        amt_70 = int(round(amt_65 * 1.42))
        amt_75 = int(round(amt_65 * 1.84))

    # 4. 損益分岐年齢と元本回収年齢の計算
    be_60_65 = (65 * amt_65 - 60 * amt_60) / (amt_65 - amt_60)
    be_65_70 = (70 * amt_70 - 65 * amt_65) / (amt_70 - amt_65)
    payback_age_65 = 65.0 + (paid_projected / amt_65) if amt_65 > 0 else 0.0

    # 5. サブタイトルと診断コメントの自動生成
    if fmt == "over_50":
        subtitle_text = (
            f"様式：50歳以上（{age_label}）｜ 60歳までの納付累計予想額：{paid_projected/10000:,.1f}万円"
            f"（現在までの累計{paid_current/10000:,.1f}万円 ＋ 60歳までの今後{remaining_years:.1f}年予想{paid_future/10000:,.1f}万円）"
        )
        comment_text = (
            "【社労士×1級FP AIスピード診断コメント（50歳以上様式：自動出力）】\n"
            f"● 60歳までの納付累計予想額と元本回収：直近の報酬ペースのまま60歳まで納付すると、今後の本人負担保険料は約{paid_future/10000:,.1f}万円（年約{annual_prem/10000:,.1f}万円）、\n"
            f" 60歳時点の納付累計予想額は「約{paid_projected/10000:,.1f}万円」となります。65歳受給（年{amt_65/10000:,.1f}万円）の場合、約{payback_age_65:.1f}歳で納付元本を回収できる計算です。\n"
            "● プロからの注意点：この見込額は60歳まで現在の報酬が継続する前提です。また年下配偶者（第3号等）がいる場合、65歳から配偶者が65歳になるまで\n"
            " 「加給年金（年約40.8万円）」が上乗せされますが、老齢厚生年金を繰り下げると加給年金が消滅するため、繰り下げるなら「老齢基礎年金のみ」の繰下げが圧倒的に有利です。"
        )
    else:
        achieved_total_man = (ext.get("current_achieved_pension_total_yen") or ((ext.get("basic_pension_yen") or 0) + (ext.get("welfare_pension_yen") or 0))) / 10000
        subtitle_text = (
            f"様式：50歳未満（現時点実績：{achieved_total_man:,.1f}万円/年）→ 60歳まで継続時の推計見込額：{amt_65/10000:,.1f}万円/年 ｜ "
            f"60歳までの納付累計予想額：{paid_projected/10000:,.1f}万円（今後追加負担{paid_future/10000:,.1f}万円）"
        )
        comment_text = (
            "【社労士×1級FP AIスピード診断コメント（50歳未満様式：自動補正・出力）】\n"
            f"● 50歳未満様式の自動補正：50歳未満の定期便には「これまでの加入実績（{achieved_total_man:,.1f}万円/年）」しか記載されていませんが、現在の加入区分で60歳（480ヶ月）まで\n"
            f" 加入し続けた場合、65歳時点の受給見込額は「約{amt_65/10000:,.1f}万円/年（月約{amt_65/12/10000:,.1f}万円）」へ増加します（本グラフは60歳まで継続後の推計値で描画しています）。\n"
            f"● 元本回収効率と注意点：60歳までの納付累計予想額「{paid_projected/10000:,.1f}万円」に対し、65歳受給開始から約{payback_age_65 - 65:.1f}年（約{payback_age_65:.1f}歳）で元本を回収できます。\n"
            " ただし、第3号被保険者の方は配偶者（年上）が65歳に達した時点（または退職時）からご自身が60歳になるまでの間、「第1号（国民年金保険料の自己負担）」に切り替わる点に要注意です！"
        )

    return {
        "title_target": label_name,
        "format_type": fmt,
        "amt_60": amt_60,
        "amt_65": amt_65,
        "amt_70": amt_70,
        "amt_75": amt_75,
        "paid_current": paid_current,
        "paid_future": paid_future,
        "paid_projected": paid_projected,
        "be_60_65": be_60_65,
        "be_65_70": be_65_70,
        "payback_age_65": payback_age_65,
        "subtitle_text": subtitle_text,
        "comment_text": comment_text,
    }