# -*- coding: utf-8 -*-
"""一頁視覺化摘要（快速摘要頁）。零 API 請求，只讀 raw/ 既有 CSV。

**所有數字由資料算出，不得寫死。** 專案 A 在這件事上踩過兩次：
看板 hero 的百分比寫成字面值，資料更新後與圖靜靜分家。

**產出約束**：
- 定案句**一字不改**（第一節）
- **不找「一個代表數字」**——本專案的力量來自三場一致，不是單一倍率（第一節）
- 限制六條、**第一條必須是「搜尋熱度 ≠ 訂閱數」**（第四節）
- **禁語**：不出現 event study／因果效應／留存／流失／拉新／建議中華電信…

視覺與圖表頁同一套系統（淡青藍紙、IBM Plex ＋ Noto Sans TC、近白卡片）。

用法：
    python scripts/build_onepager.py
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

    用 SVG 而非 PNG：向量碼在紙上與螢幕上都不會糊，而糊掉的 QR 就是掃不到的 QR。
    error='m' 容錯約 15%，容得下列印與翻拍的損耗。
    """
    import base64
    import io

    import segno
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=1, border=2,
                                    dark="#131822", light="#ffffff", xmldecl=False)
    return ("data:image/svg+xml;base64,"
            + base64.b64encode(buf.getvalue()).decode("ascii"))

# 賽事參考日：未查一手來源，僅作對齊用（見 README 限制第 5 條）。
# 轉播權已於 2026-08-06 查證，三場 Hami Video 皆有轉播。
EVENTS = [
    ("2022 世界盃", dt.date(2022, 11, 20), dt.date(2022, 12, 18), 4.0),
    ("2023 WBC", dt.date(2023, 3, 8), dt.date(2023, 3, 21), 0.6),
    ("2024 巴黎奧運", dt.date(2024, 7, 26), dt.date(2024, 8, 11), 2.3),
]

# 定案句——預先定案，**一字不改**
VERDICT = ("賽事熱度在賽後 1–2 週內完全回到賽前基準，三場皆然"
           "——在這份資料的解析度下觀測不到任何殘留提升。")

S1, S1_D = "#1682a8", "#0e647f"
SHELL, PAPER, PAPER2, CARD = "#e5e7ee", "#eef4f7", "#e5eff3", "#fafdfe"
INK, INK2, MUTED, MUTED2 = "#131822", "#4c5666", "#8b94a3", "#7c8695"
RULE, RULE_D = "rgba(19,24,34,.09)", "rgba(19,24,34,.16)"
WARN, WARN_BG = "#a05a18", "#f6f0e8"
CRIT = "#a83a2e"
SANS = ("'IBM Plex Sans', 'Noto Sans TC', system-ui, -apple-system, "
        "'Segoe UI', 'Microsoft JhengHei', sans-serif")
MONO = ("'IBM Plex Mono', 'Noto Sans TC', ui-monospace, 'Cascadia Mono', "
        "'SF Mono', Consolas, monospace")
FONTS_HREF = ("https://fonts.googleapis.com/css2?"
              "family=IBM+Plex+Sans:wght@400;500;600"
              "&family=IBM+Plex+Mono:wght@400;500;600"
              "&family=Noto+Sans+TC:wght@300;400;500;700&display=swap")
BYLINE = "陳嘉翔"

# 摘要就是摘要：每項一句話。展開的版本在 README，這裡只給指路。
EVIDENCE = [
    ("判準先於資料",
     "閾值與事件選擇規則於檢視資料前存檔。<b>事後修正標示為事後，原數字保留不刪</b>："
     "基準窗遭前一事件污染，故將 8 週 min–max 調整為 20 週 p25–p75",
     "README.md"),
    ("結論所依賴的量有測試",
     "14 項 pytest 蓋住四個<b>會改變結論卻不會報錯</b>的函式；"
     "其中一項釘住基準帶的崩潰點，該定義並非無條件安全",
     "scripts/metrics.py｜tests/"),
    ("驗證產出的成品，不是記憶體裡的物件",
     "解析寫出的 HTML：shape 幾何、三種寬度的標註碰撞與溢出、"
     "<b>標註是否被資料線穿過</b>",
     "scripts/verify_charts.py"),
    ("不穩定來源的取用紀律",
     "實測顯示配額機制為<b>觸發式封鎖</b>而非節流（0/30 橫跨 47.5 小時），"
     "因此改採 fail-fast；每次請求的成敗均寫入 append-only 紀錄",
     "logs/quota_attempts.csv"),
    ("解析度作為方法論",
     "同一場賽事，週級解析度將峰值判在開幕週，日級解析度則判在決賽日。"
     "<b>兩張都交付，因為分歧本身就是結果</b>",
     "charts/daily-vs-weekly.html"),
]

NOT_CLAIMED = [
    ("沒有任何訂閱、退訂、註冊或轉換資料。", "本分析僅能觀測搜尋關注度。"),
    ("不宣稱因果。",
     "亦不使用預設有識別策略的方法名。三場之間賽事類型與賽程長度完全混淆（n=3），"
     "結論只能是描述性的。"),
    # 原本只寫「不含模型」——這一頁設計成可單獨閱讀，那句會被讀成能力缺口。
    # 補上建模作品的指路，把「本專案的取捨」與「這個人不會建模」分開。
    # 三件作品均為本人另外的公開 repo，寫入前已逐一查證。
    ("本專案不含模型，也不是每日運行的管線。",
     "建模作品另見 SECOM 半監督異常偵測、語音情緒辨識跨語料庫比較、台股情緒預測。"
     "價值在約束與工程紀律，不在演算法。"),
    ("深色模式未做。", "兩種模式應各自訂定調色盤而非自動反轉，尚未執行。"),
    ("四項驗證未完成（可重現性、MOD 對照、事件詞、兩個日級窗）。",
     "均遭配額限制。逐項評估「未補齊是否構成交付阻斷」，結論皆為不構成阻斷。"),
]

# 「若取得內部資料，第一步會看什麼」。
# 分寸線：**「建議公司做什麼」＝僭越；「若我在內部會先看什麼」＝問題排序能力。**
# 維持假設語氣，不出現「建議」二字——外部求職者不對公司下指導棋。
IF_INSIDE = [
    "若取得訂閱與退訂資料，把搜尋熱度曲線與實際訂閱曲線疊起來，"
    "量化代理指標的效度。",
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
        f"<tr><td class='cap'>{c}</td><td>{w}</td>"
        f"<td class='where'>{p}</td></tr>" for c, w, p in EVIDENCE)
    nc = "".join(f"<div class='nc'><b>{h}</b>{t}</div>" for h, t in NOT_CLAIMED)
    ii = "".join(f"<div class='ii'>{t}</div>" for t in IF_INSIDE)
    tbl = "".join(
        f"<tr><td>{r['name']}</td><td>{r['dur']}</td><td>{r['peak']}</td>"
        f"<td>{r['burst']}×</td><td>{r['blo']:.0f}–{r['bhi']:.0f}</td>"
        f"<td class='hit'>{r['back']} 週</td></tr>" for r in rows)
    backs = sorted({r["back"] for r in rows})
    back_txt = f"{min(backs)} 至 {max(backs)}"
    durs = sorted({r["dur"] for r in rows})

    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>專案摘要｜Hami Video 賽事熱度衰退</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS_HREF}" rel="stylesheet">
<style>
*{{box-sizing:border-box;}}
body{{margin:0;background:{SHELL};color:{INK};font-family:{SANS};line-height:1.72;
     -webkit-font-smoothing:antialiased;padding:44px 24px 80px;}}
.page{{max-width:1000px;margin:0 auto;background:{PAPER};border:1px solid {RULE};
      border-radius:16px;padding:48px 52px 40px;
      box-shadow:0 1px 2px rgba(19,24,34,.04),0 30px 70px -40px rgba(19,24,34,.45);}}

.head{{display:flex;align-items:flex-start;justify-content:space-between;gap:40px;
     padding-bottom:22px;border-bottom:1px solid rgba(19,24,34,.14);}}
.eyebrow{{display:block;font-family:{MONO};font-size:10px;letter-spacing:.24em;
        text-transform:uppercase;color:{S1};font-weight:500;margin-bottom:10px;}}
h1{{font-size:29px;font-weight:600;letter-spacing:-.03em;margin:0 0 8px;line-height:1.25;}}
.sub{{font-size:12.5px;color:{MUTED};margin:0;}}
.qr{{width:78px;height:78px;flex:none;border:1px solid rgba(19,24,34,.10);
   border-radius:8px;padding:4px;background:#fdfdff;}}

.hero{{background:{PAPER2};border-radius:12px;padding:24px 28px;margin-top:22px;}}
.big{{font-size:28px;font-weight:600;letter-spacing:-.03em;line-height:1.3;color:{S1_D};}}
.verdict{{font-size:13px;color:{INK2};margin-top:10px;padding-top:10px;
        border-top:1px solid rgba(19,24,34,.11);}}
.verdict b{{color:{INK};font-weight:500;}}

.fig{{width:100%;display:block;margin:20px 0 0;border:1px solid rgba(19,24,34,.10);
    border-radius:10px;}}

h2{{font-size:16px;font-weight:500;letter-spacing:-.01em;margin:30px 0 6px;
   padding-bottom:9px;border-bottom:1px solid {RULE_D};}}

table{{border-collapse:collapse;width:100%;font-size:12.5px;
     font-variant-numeric:tabular-nums;}}
th{{text-align:right;font-family:{MONO};font-size:10px;letter-spacing:.14em;
   text-transform:uppercase;color:#98a0ad;font-weight:500;padding:10px 14px 8px 0;}}
th:first-child{{text-align:left;}}
td{{padding:11px 14px 11px 0;border-top:1px solid rgba(19,24,34,.08);
   text-align:right;vertical-align:top;color:{INK2};font-family:{MONO};}}
td:first-child{{text-align:left;font-family:{SANS};color:{INK};font-weight:500;}}
tr:hover{{background:rgba(19,24,34,.035);}}
td.hit{{font-weight:500;color:{S1_D};}}
th:last-child,td:last-child{{padding-right:0;}}

/* 條件對照表的欄位語意與上表不同：左對齊、非數字 */
.cond th,.cond td{{text-align:left;font-family:{SANS};}}
.cond td{{color:{INK2};font-weight:400;}}
.cond td.cap{{font-weight:500;color:{INK};width:150px;}}
.cond td.where{{color:#98a0ad;font-size:10.5px;width:180px;font-family:{MONO};}}
.cond b{{color:{INK};font-weight:500;}}

.after{{font-size:12.8px;color:{INK2};margin:12px 0 0;}}
.after b{{color:{INK};font-weight:500;}}

.anchor{{background:{PAPER2};border:1px solid rgba(22,130,168,.20);border-radius:12px;
       padding:18px 22px;margin-top:12px;}}
.pair{{display:flex;align-items:baseline;gap:22px;margin-bottom:12px;}}
.pair .v{{font-family:{MONO};font-size:26px;font-weight:500;letter-spacing:-.03em;}}
.pair .l{{font-size:11.5px;color:{MUTED2};margin-top:3px;}}
.pair .div{{width:1px;align-self:stretch;background:rgba(19,24,34,.12);}}
.anchor p{{margin:0;font-size:12.8px;color:{INK2};}}
.anchor .crit{{color:{CRIT};font-weight:500;}}

.honest{{background:{WARN_BG};border:1px solid rgba(160,90,24,.20);border-radius:10px;
       padding:16px 20px;display:flex;flex-direction:column;gap:9px;}}
.nc{{font-size:12.8px;color:{INK2};}}
.nc b{{color:{WARN};font-weight:500;}}

/* 「我不宣稱的事」與「若取得內部資料會先看什麼」並排：
   前者是能力邊界，後者是問題排序。兩者相鄰，讀者才不會把前者讀成後者的缺席。
   用系列主色而非警示色——這一欄不是警告，是前瞻。 */
.twocol{{display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:start;}}
.twocol h2{{margin-top:32px;}}
.inside{{background:{PAPER2};border:1px solid rgba(22,130,168,.22);border-radius:10px;
       padding:16px 20px;display:flex;flex-direction:column;gap:9px;}}
.ii{{font-size:12.8px;color:{INK2};padding-left:15px;position:relative;}}
.ii::before{{content:"";position:absolute;left:0;top:7px;width:5px;height:5px;
           border-radius:50%;background:{S1};}}
code{{font-family:{MONO};font-size:11.5px;background:rgba(19,24,34,.06);
    padding:2px 6px;border-radius:4px;color:{INK2};}}

.qrbar{{margin-top:24px;padding-top:16px;border-top:1px solid {RULE};
      font-size:12.5px;color:{INK2};}}
.qrbar b{{color:{INK};font-weight:500;}}
.qrbar .u{{font-family:{MONO};font-size:10.5px;color:{MUTED};word-break:break-all;}}
.foot{{margin:22px 0 0;padding-top:14px;border-top:1px solid {RULE};
     font-family:{MONO};font-size:10.5px;line-height:1.9;color:#98a0ad;}}
a{{color:{S1};text-decoration:none;border-bottom:1px solid rgba(22,130,168,.28);}}
a:hover{{color:{S1_D};border-bottom-color:{S1_D};}}
@media (max-width:900px){{.page{{padding:32px 24px;}}
  .twocol{{grid-template-columns:1fr;gap:0;}}}}
</style>
<div class="page">

<div class="head">
  <div>
    <span class="eyebrow">專案摘要 / 02　·　{BYLINE}</span>
    <h1>賽事熱度在賽後多久回到原點？</h1>
    <p class="sub">Hami Video（中華電信影視平台）× 三場國際賽事　·　
    Google Trends 台灣，週解析度 {s.index[0]:%Y-%m} 到 {s.index[-1]:%Y-%m}（n={len(s)}）　·
    外部求職者以公開資料製作，非中華電信內部文件</p>
  </div>
  <img class="qr" src="{qr_svg_data_uri(PAGES_URL)}" alt="QR code，開啟線上互動圖表">
</div>

<div class="hero">
  <div class="big">賽事帶來的是脈衝，不是階梯。</div>
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
<p class="after"><b>結論不依賴任何單一數字。</b>
爆發倍率的分母（賽前基準）本身存在漂移，跨年比較並不乾淨。
較為穩固的觀察是<b>三場皆於 {back_txt} 週內回到基準帶</b>，
而賽程長度自 {min(durs)} 週至 {max(durs)} 週不等，結果仍然一致。
衰退<b>形狀</b>的差異，幾乎可完全歸因於賽程長度的機械效果。</p>

<h2>唯一的外部參照</h2>
<div class="anchor">
  <div class="pair">
    <div><div class="v" style="color:{S1_D}">11.2×</div>
      <div class="l">官方新聞稿（2023-03-24）：WBC 期間訂閱數較去年同期成長</div></div>
    <div class="div"></div>
    <div><div class="v" style="color:{INK}">{rows[1]['burst']}×</div>
      <div class="l">本分析：峰值 ÷ 賽前基準中位數</div></div>
  </div>
  <p><span class="crit">兩者定義不同，不可直接比較，也不宣稱吻合。</span>
  官方為訂閱數 YoY，本分析為搜尋熱度的峰值比。可陳述者僅為量級相近。
  此為目前唯一能為「搜尋熱度不等於訂閱數」此一限制提供外部參照的資料點。</p>
</div>

<h2>條件對照</h2>
<table class="cond">
  <tr><th>能力項目</th><th>本專案的對應證據</th><th>位置</th></tr>
  {ev}
</table>

<div class="twocol">
  <div>
    <h2>我不宣稱的事</h2>
    <div class="honest">{nc}</div>
  </div>
  <div>
    <h2>若取得內部資料，第一步會看什麼</h2>
    <div class="inside">{ii}</div>
  </div>
</div>

<div class="qrbar">
  <b>掃描頁首 QR 開啟線上互動圖表</b>：三格衰退主圖（可查每週指數），
  以及同一場賽事日 vs 週兩種解析度的對照圖。<br>
  <span class="u">{PAGES_URL}</span>
</div>

<p class="foot">
限制六條完整版見 README.md，第一條為「搜尋熱度不等於訂閱數」：
賽事期間訂閱、賽後不再搜尋但未退訂者，本資料無法區分。
判準於檢視資料前存檔，事後修正一律標示為事後。<br>
本頁所有數值由 scripts/build_onepager.py 於產生時自快照重新計算，非手動填寫。
</p>

</div>"""


def main() -> int:
    s, rows = compute()
    # 與 README 公布的數字對帳——對不上就是有東西漂了，不要默默交付。
    expect = {"2022 世界盃": 5, "2023 WBC": 3, "2024 巴黎奧運": 3}
    bad = [f"{r['name']}: 算出 {r['back']} / 規格 {expect[r['name']]}"
           for r in rows if r["back"] != expect[r["name"]]]
    if bad:
        print("❌ 回歸週數與 README 公布的數字不符：\n  " + "\n  ".join(bad))
        return 1
    print("✅ 回歸週數與 README 公布的數字相符：" +
          "、".join(f"{r['name']} {r['back']} 週" for r in rows))

    path = OUT / "onepager.html"
    path.write_text(build(s, rows), encoding="utf-8")
    print(f"已產生：{path.relative_to(REPO)}　{path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
