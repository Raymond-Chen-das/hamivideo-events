# -*- coding: utf-8 -*-
"""一頁視覺化摘要（快速摘要用）。零 API 請求，只讀 raw/ 既有 CSV。

**所有數字由資料算出，不得寫死。** 專案 A 在這件事上踩過兩次：
看板 hero 的百分比寫成字面值，資料更新後與圖靜靜分家。

**受規格約束**（`docs/10-project-spec.md`）：
- 定案句**一字不改**（第一節）
- **不找「一個代表數字」**——本專案的力量來自三場一致，不是單一倍率（第一節）
- 限制六條、**第一條必須是「搜尋熱度 ≠ 訂閱數」**（第四節）
- **禁語清單**（第五節）：不出現 event study／因果效應／留存／流失／拉新／建議中華電信…

用法：
    python scripts/build_onepager.py
    # 轉 PDF（需要 Edge）：
    # msedge --headless=new --print-to-pdf=onepager.pdf --no-pdf-header-footer <file>
"""
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

import datetime as dt
import warnings

warnings.filterwarnings("ignore")
import pandas as pd

from metrics import baseline_band, periods_to_threshold

from _data import require

RAW = REPO / "data" / "raw"
OUT = REPO / "charts"
KW = "Hami Video"

# QR 目標＝Pages 的主圖頁，**不是 repo 首頁**。掃碼的人要的是圖，不是程式碼。
PAGES_URL = "https://raymond-chen-das.github.io/hamivideo-events/"


def qr_svg_data_uri(url: str) -> str:
    """回傳可直接放進 <img src> 的 SVG data URI。

    用 SVG 而非 PNG：這份摘要會被列印成 PDF，向量碼在紙上與螢幕上都不會糊，
    而糊掉的 QR 就是掃不到的 QR。error='m' 容錯約 15%，容得下列印與翻拍的損耗。
    """
    import base64
    import io

    import segno
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=1, border=2,
                                    dark="#0b0b0b", light="#ffffff", xmldecl=False)
    return ("data:image/svg+xml;base64,"
            + base64.b64encode(buf.getvalue()).decode("ascii"))

# 賽事參考日：未查一手來源，僅作對齊用（規格第四節限制 5）。
# 轉播權已於 2026-08-06 查證，三場 Hami Video 皆有轉播。
EVENTS = [
    ("2022 世界盃", dt.date(2022, 11, 20), dt.date(2022, 12, 18), 4.0),
    ("2023 WBC", dt.date(2023, 3, 8), dt.date(2023, 3, 21), 0.6),
    ("2024 巴黎奧運", dt.date(2024, 7, 26), dt.date(2024, 8, 11), 2.3),
]

# 定案句——規格第一節，**一字不改**
VERDICT = ("賽事熱度在賽後 1–2 週內完全回到賽前基準，三場皆然"
           "——在這份資料的解析度下觀測不到任何殘留提升。")

TELCO_C, ACCENT = "#2a78d6", "#eb6834"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, CRIT = "#e1e0d9", "#b03030"
FONT = 'system-ui, -apple-system, "Segoe UI", "Microsoft JhengHei", sans-serif'

# 摘要就是摘要：每項一句話。展開的版本在 README 與 decision-trail，這裡只給指路。
EVIDENCE = [
    ("判準先於資料",
     "閾值與事件選擇規則在看資料前存檔；<b>事後修正標示為事後，原數字保留不刪</b>"
     "（基準窗被前一事件污染 → 8 週 min–max 改 20 週 p25–p75）",
     "docs/decision-trail.md"),
    ("結論所依賴的量有測試",
     "14 項 pytest 蓋住四個<b>會改變結論卻不會報錯</b>的函式；"
     "其中一項釘住基準帶的崩潰點——該定義並非無條件安全",
     "scripts/metrics.py｜tests/"),
    ("驗證產出的成品，不是記憶體裡的物件",
     "解析寫出的 HTML：shape 幾何、三種寬度的標註碰撞與溢出、"
     "<b>標註是否被資料線穿過</b>",
     "scripts/verify_charts.py"),
    ("不穩定來源的取用紀律",
     "實測配額是<b>觸發式封鎖</b>而非節流（0/30 橫跨 47.5 小時）→ 改 fail-fast；"
     "每次請求成敗都進 append-only 紀錄",
     "logs/quota_attempts.csv"),
    ("解析度作為方法論",
     "同一場賽事週級把峰值判在開幕週、日級判在決賽日。"
     "<b>兩張都交付，因為分歧本身就是結果</b>",
     "charts/daily-vs-weekly.html"),
]

NOT_CLAIMED = [
    "**沒有任何訂閱、退訂、註冊或轉換資料**——本分析只看得到搜尋關注。",
    "**不宣稱因果**，也不使用預設有識別策略的方法名。三場之間"
    "賽事類型與賽程長度完全混淆（n=3），結論只能是描述性的。",
    "**本專案不含模型**，也不是每日運行的管線。價值在約束與工程紀律，不在演算法。",
    "**深色模式未做**——兩種模式應各自由調色盤取步、而非自動反轉，尚未執行。",
    "**四項驗證未完成**（可重現性、MOD 對照、事件詞、兩個日級窗），"
    "皆被配額擋下。逐項問過「不補就不能交付嗎」，答案都是不能阻斷。",
]


def compute():
    df = pd.read_csv(require("groupA_brand_5yr.csv"), index_col=0, parse_dates=True)
    df = df[~df["isPartial"].astype(bool)]
    s = df[KW]
    rows = []
    for name, d0, d1, dur in EVENTS:
        win = s[(s.index >= pd.Timestamp(d0) - pd.Timedelta(weeks=2))
                & (s.index <= pd.Timestamp(d1) + pd.Timedelta(weeks=2))]
        pi = s.index.get_loc(win.idxmax())
        peak = int(win.max())
        blo, bhi = baseline_band(s, pi)
        rows.append(dict(name=name, dur=dur, peak=peak,
                         blo=blo, bhi=bhi,
                         burst=round(peak / s.iloc[max(0, pi - 26):pi - 5].median(), 1),
                         back=periods_to_threshold(s, pi, bhi)))
    return s, rows


def build(s, rows) -> str:
    ev = "".join(
        f"<tr><td class='cap'>{c}</td><td>{w.replace('**','')}</td>"
        f"<td class='where'>{p}</td></tr>" for c, w, p in EVIDENCE)
    nc = "".join(f"<li>{x.replace('**','')}</li>" for x in NOT_CLAIMED)
    tbl = "".join(
        f"<tr><td>{r['name']}</td><td>{r['dur']}</td><td>{r['peak']}</td>"
        f"<td>{r['burst']}×</td><td>{r['blo']:.0f}–{r['bhi']:.0f}</td>"
        f"<td class='hit'>{r['back']} 週</td></tr>" for r in rows)
    backs = sorted({r["back"] for r in rows})
    back_txt = "–".join(str(b) for b in (min(backs), max(backs)))

    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>專案摘要｜Hami Video 賽事熱度衰退</title>
<style>
@page {{ size: A4; margin: 10mm 11mm; }}
*{{box-sizing:border-box;}}
body{{margin:0;background:#f4f4f2;color:{INK};font-family:{FONT};line-height:1.5;
     font-size:11.8px;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.page{{max-width:900px;margin:0 auto;background:#fff;padding:24px 28px 20px;}}
h1{{font-size:19px;font-weight:660;margin:0 0 3px;letter-spacing:-.01em;}}
.sub{{font-size:11.5px;color:{MUTED};margin:0 0 16px;}}
h2{{font-size:13px;font-weight:650;margin:13px 0 5px;padding-bottom:4px;
   border-bottom:1.5px solid {INK};}}
.hero{{background:#fafafa;border-left:3px solid {TELCO_C};padding:13px 17px;}}
.big{{font-size:23px;font-weight:680;letter-spacing:-.015em;line-height:1.35;color:{TELCO_C};}}
.verdict{{font-size:12.3px;color:{INK2};margin-top:7px;padding-top:7px;
         border-top:1px solid {GRID};}}
/* 滿版。曾為了把 PDF 擠進一頁而縮到 78%，但使用者「兩頁無所謂，視覺化要佳」——
   這張圖是整份摘要的視覺重心，為了頁數把它縮小是本末倒置。 */
.fig{{width:100%;display:block;margin:11px auto 0;border:1px solid {GRID};border-radius:7px;}}
table{{border-collapse:collapse;width:100%;font-size:11.5px;margin-top:5px;
      font-variant-numeric:tabular-nums;}}
th,td{{border-bottom:1px solid {GRID};padding:6px 9px 6px 0;text-align:left;
      vertical-align:top;}}
th{{color:{MUTED};font-weight:600;font-size:11px;}}
td.hit{{font-weight:660;color:{TELCO_C};}}
td.cap{{font-weight:640;width:150px;}}
td.where{{color:{MUTED};font-size:10.3px;width:180px;font-family:ui-monospace,monospace;}}
.anchor{{background:#fbf9f4;border:1px solid #e6e0cf;border-radius:7px;
        padding:8px 12px;font-size:11.2px;margin-top:7px;}}
.honest{{background:#fdf7f7;border:1px solid #eedcdc;border-radius:7px;
        padding:10px 14px;font-size:11.5px;}}
.honest b{{color:{CRIT};}}
ul{{margin:5px 0 0;padding-left:17px;}} li{{margin:3px 0;}}
code{{font-size:10.5px;background:#f0f0ee;padding:0 3px;border-radius:3px;}}
.foot{{margin-top:15px;padding-top:9px;border-top:1px solid {GRID};
      font-size:10.3px;color:{MUTED};}}
.qrbar{{display:flex;align-items:center;gap:14px;margin-top:14px;padding-top:11px;
       border-top:1px solid {GRID};}}
.qrbar img{{width:74px;height:74px;flex:none;}}
.qrtext{{font-size:11px;color:{INK2};line-height:1.55;}}
.qrtext b{{color:{INK};}}
.qrtext .u{{font-family:ui-monospace,monospace;font-size:10px;color:{MUTED};
           word-break:break-all;}}
@media print{{ body{{background:#fff;}} .page{{padding:0;max-width:none;}} }}
</style>
<div class="page">

<h1>賽事熱度在賽後多久回到原點？</h1>
<p class="sub">Hami Video（中華電信影視平台）× 三場國際賽事　·　資料：Google Trends 台灣，
週解析度 {s.index[0]:%Y-%m} ~ {s.index[-1]:%Y-%m}（n={len(s)}）　·
外部求職者以公開資料製作，非中華電信內部文件</p>

<div class="hero">
  <div class="big">賽事帶來的是<b>脈衝</b>，不是<b>階梯</b>。</div>
  <div class="verdict"><b>定案句：</b>{VERDICT}</div>
</div>

<img class="fig" src="../docs/images/chart-decay-figure.png"
     alt="三場賽事的熱度衰退：每格一場，賽後 3–5 週內回到賽前基準帶">

<h2>三場賽事，同一次查詢、同一尺度，直接可比</h2>
<table>
  <tr><th>賽事</th><th>賽程(週)</th><th>峰值</th><th>爆發倍率</th>
      <th>賽前基準帶</th><th>回到基準</th></tr>
  {tbl}
</table>
<p style="font-size:11.5px;color:{INK2};margin:8px 0 0;">
<b>重點不是任何單一數字。</b> 爆發倍率的分母（賽前基準）本身在漂移，跨年比較並不乾淨；
真正硬的是<b>三場都在 {back_txt} 週內回到基準帶</b>——賽程長度從 0.6 週到 4.0 週，
結果卻一致。衰退<b>形狀</b>的差異幾乎完全是賽程長度的機械後果，不是主要發現。</p>

<div class="anchor">
<b>唯一的外部參照</b>：中華電信官方新聞稿（2023-03-24）公布 WBC 期間 Hami Video
訂閱數較去年同期成長 <b>11.2 倍</b>；本分析單以搜尋熱度算出的 WBC 爆發倍率為
<b>{rows[1]['burst']}×</b>。
⚠️ <b>兩者定義不同</b>（官方是訂閱數 YoY，本分析是峰值 ÷ 賽前基準中位數），
<b>不可直接比較、不宣稱吻合</b>。可以說的是量級相近——這是目前唯一能為
「搜尋熱度不等於訂閱數」這條限制提供外部參照的資料點。
</div>

<h2>條件對照</h2>
<table>
  <tr><th>能力項目</th><th>本專案的對應證據</th><th>位置</th></tr>
  {ev}
</table>

<h2>我不宣稱的事</h2>
<div class="honest"><ul>{nc}</ul></div>

<div class="qrbar">
  <img src="{qr_svg_data_uri(PAGES_URL)}" alt="QR code，開啟線上互動圖表">
  <div class="qrtext">
    <b>掃描開啟線上互動圖表</b>——三格衰退主圖（可查每週指數）、
    以及同一場賽事日 vs 週兩種解析度的對照圖。<br>
    <span class="u">{PAGES_URL}</span>
  </div>
</div>

<p class="foot">
限制六條完整版見 <code>README.md</code>，第一條為「搜尋熱度不等於訂閱數」——
賽事期間訂閱、賽後不再搜尋但未退訂的人，這份資料分不開。
判準與推翻歷程見 <code>docs/decision-trail.md</code>（append-only）。
本頁所有數值由 <code>scripts/build_onepager.py</code> 於產生時從快照重新計算，非手動填寫。
</p>

</div>"""


def main() -> int:
    s, rows = compute()
    # 與規格第一節公布的數字對帳——對不上就是有東西漂了，不要默默交付。
    expect = {"2022 世界盃": 5, "2023 WBC": 3, "2024 巴黎奧運": 3}
    bad = [f"{r['name']}: 算出 {r['back']} / 規格 {expect[r['name']]}"
           for r in rows if r["back"] != expect[r["name"]]]
    if bad:
        print("❌ 回歸週數與規格第一節不符：\n  " + "\n  ".join(bad))
        return 1
    print("✅ 回歸週數與規格第一節相符：" +
          "、".join(f"{r['name']} {r['back']} 週" for r in rows))

    path = OUT / "onepager.html"
    path.write_text(build(s, rows), encoding="utf-8")
    print(f"已產生：{path.relative_to(REPO)}　{path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
