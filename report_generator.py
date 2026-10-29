# report_generator.py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.font_manager as fm

def setup_japanese_font():
    """環境にある見栄えの良い日本語フォントを自動選択する"""
    preferred_fonts = [
        "Rounded Mgen+ 2cp", "BIZ UDPGothic", "Meiryo", 
        "Yu Gothic", "MS Gothic", "Noto Sans CJK JP", "Hiragino Sans"
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in preferred_fonts:
        if font in available:
            plt.rcParams["font.family"] = "sans-serif"
            plt.rcParams["font.sans-serif"] = [font]
            break
    plt.rcParams["axes.unicode_minus"] = False

def generate_pension_report(calc_data: dict, output_filename: str = "nenkin_report.png"):
    """計算結果データから診断レポート画像を生成・保存する"""
    setup_japanese_font()

    name_label = calc_data["title_target"]
    amt_60 = calc_data["amt_60"]
    amt_65 = calc_data["amt_65"]
    amt_70 = calc_data["amt_70"]
    amt_75 = calc_data["amt_75"]
    paid_current = calc_data["paid_current"]
    paid_future = calc_data["paid_future"]
    paid_projected = calc_data["paid_projected"]
    be_60_65 = calc_data["be_60_65"]
    be_65_70 = calc_data["be_65_70"]
    payback_age_65 = calc_data["payback_age_65"]
    subtitle_text = calc_data["subtitle_text"]
    comment_text = calc_data["comment_text"]

    ages = np.arange(60, 91)
    cum_60_cont = np.maximum(0, ages - 60) * amt_60 / 10000
    cum_65_cont = np.maximum(0, ages - 65) * amt_65 / 10000
    cum_70_cont = np.maximum(0, ages - 70) * amt_70 / 10000

    be1_y = (be_60_65 - 65) * amt_65 / 10000
    be2_y = (be_65_70 - 65) * amt_65 / 10000

    fig = plt.figure(figsize=(14, 8.4), dpi=150)
    fig.patch.set_facecolor("#F8FAFC")

    fig.suptitle(
        f"【AIスピード診断】ねんきん定期便 繰上げ・繰下げ受給シミュレーション（{name_label}）",
        fontsize=16.5, fontweight="bold", color="#1E293B", y=0.96
    )
    plt.figtext(
        0.5, 0.908, subtitle_text,
        ha="center", fontsize=10, color="#334155",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#E2E8F0", edgecolor="none")
    )

    # 左グラフ：受給開始年齢別の年額・月額比較
    ax1 = plt.subplot2grid((12, 12), (1, 0), rowspan=8, colspan=5)
    ax1.set_facecolor("#FFFFFF")
    labels = ["60歳開始\n(繰上げ ▲24%)", "65歳開始\n(60歳まで継続見込)", "70歳開始\n(繰下げ +42%)", "75歳開始\n(参考: +84%)"]
    values_man = [amt_60 / 10000, amt_65 / 10000, amt_70 / 10000, amt_75 / 10000]
    colors = ["#64748B", "#2563EB", "#0D9488", "#D97706"]

    bars = ax1.bar(labels, values_man, color=colors, width=0.55, zorder=3)
    ax1.grid(axis="y", linestyle="--", alpha=0.5, zorder=0)
    max_bar = max(values_man)
    ax1.set_ylim(0, max_bar * 1.22)
    ax1.set_ylabel("年間受給額（万円 / 年）", fontsize=11, fontweight="bold", color="#334155")
    ax1.set_title("① 受給開始年齢別の「年額・月額」見込", fontsize=13, fontweight="bold", color="#1E293B", pad=12)

    for bar, val, raw_val in zip(bars, values_man, [amt_60, amt_65, amt_70, amt_75]):
        monthly = raw_val / 12 / 10000
        ax1.text(
            bar.get_x() + bar.get_width() / 2, val + max_bar * 0.02,
            f"{val:,.1f}万円/年\n(月 約{monthly:.1f}万円)",
            ha="center", va="bottom", fontsize=9.5, fontweight="bold", color="#1E293B"
        )

    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["left"].set_color("#CBD5E1")
    ax1.spines["bottom"].set_color("#CBD5E1")

    # 右グラフ：年齢別の累計受給額推移
    ax2 = plt.subplot2grid((12, 12), (1, 6), rowspan=8, colspan=6)
    ax2.set_facecolor("#FFFFFF")

    ax2.plot(ages, cum_60_cont, label=f"60歳繰上げ (年{amt_60/10000:,.1f}万円)", color="#64748B", linewidth=2.5, linestyle="--")
    ax2.plot(ages, cum_65_cont, label=f"65歳本来受給 (年{amt_65/10000:,.1f}万円)", color="#2563EB", linewidth=3.0)
    ax2.plot(ages, cum_70_cont, label=f"70歳繰下げ (年{amt_70/10000:,.1f}万円)", color="#0D9488", linewidth=3.0)

    proj_man = paid_projected / 10000
    curr_man = paid_current / 10000
    ax2.axhline(proj_man, color="#DC2626", linestyle="-.", linewidth=2.0, label=f"60歳までの納付累計予想額 ({proj_man:,.1f}万円)")
    if paid_future > 0:
        ax2.axhline(curr_man, color="#F59E0B", linestyle=":", linewidth=1.5, label=f"うち現在までの納付済額 ({curr_man:,.1f}万円)")

    ax2.scatter([payback_age_65], [proj_man], color="#DC2626", marker="D", s=55, zorder=5)
    ax2.annotate(
        f"65歳受給の元本回収\n約{payback_age_65:.1f}歳",
        xy=(payback_age_65, proj_man),
        xytext=(max(61, payback_age_65 - 7.5), proj_man + max(cum_70_cont) * 0.08),
        arrowprops=dict(arrowstyle="->", color="#DC2626", lw=1.2),
        fontsize=9, fontweight="bold", color="#991B1B",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#FEF2F2", edgecolor="#FCA5A5")
    )

    ax2.scatter([be_60_65, be_65_70], [be1_y, be2_y], color="#2563EB", s=65, zorder=5)
    ax2.annotate(
        f"65歳が60歳を逆転\n約{be_60_65:.1f}歳 (累計{be1_y:,.0f}万円)",
        xy=(be_60_65, be1_y), xytext=(be_60_65 - 9.5, be1_y + max(cum_70_cont) * 0.12),
        arrowprops=dict(arrowstyle="->", color="#1E40AF", lw=1.5),
        fontsize=9, fontweight="bold", color="#1E3A8A",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#EFF6FF", edgecolor="#93C5FD")
    )

    ax2.annotate(
        f"70歳が65歳を逆転\n約{be_65_70:.1f}歳 (累計{be2_y:,.0f}万円)",
        xy=(be_65_70, be2_y), xytext=(be_65_70 - 3.0, be2_y - max(cum_70_cont) * 0.22),
        arrowprops=dict(arrowstyle="->", color="#0F766E", lw=1.5),
        fontsize=9, fontweight="bold", color="#115E59",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#F0FDFA", edgecolor="#5EEAD4")
    )

    ax2.set_title("② 年齢別の「累計受給額」と元本回収・損益分岐ライン", fontsize=13, fontweight="bold", color="#1E293B", pad=12)
    ax2.set_xlabel("年齢（歳）", fontsize=11, fontweight="bold", color="#334155")
    ax2.set_ylabel("累計金額（万円）", fontsize=11, fontweight="bold", color="#334155")
    ax2.set_xlim(60, 90)
    ax2.set_ylim(0, max(cum_70_cont) * 1.08)
    ax2.yaxis.set_major_formatter(ticker.StrMethodFormatter("{x:,.0f}"))
    ax2.grid(True, linestyle="--", alpha=0.5)
    ax2.legend(loc="upper left", frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", fontsize=8.8)

    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["left"].set_color("#CBD5E1")
    ax2.spines["bottom"].set_color("#CBD5E1")

    plt.figtext(
        0.03, 0.015, comment_text, fontsize=9.2, color="#1E293B", linespacing=1.45,
        bbox=dict(boxstyle="round,pad=0.6", facecolor="#EFF6FF", edgecolor="#93C5FD", linewidth=1.5)
    )

    plt.subplots_adjust(left=0.06, right=0.97, top=0.84, bottom=0.22, wspace=0.25)
    plt.savefig(output_filename, dpi=150)
    plt.close(fig)
    print(f"レポート画像を出力しました: {output_filename}")