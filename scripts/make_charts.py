# -*- coding: utf-8 -*-
"""產生兩張圖表（HTML + Plotly）。零 API 請求，只讀 raw/ 既有 CSV。
A：三格 small multiples（主視覺）
C：世足 日 vs 週（方法論，第二張）

草稿 B（疊合正規化曲線）已於 2026-08-05 刪除：它強調的「發散」只是賽程長度的翻譯，
且第 3 週後三條曲線全部壓在 5.6–6.5%，七成畫布零資訊。
編號保留 A/C 不重排，避免與既有 commit 訊息對不上。
"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import warnings, datetime as dt
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from metrics import baseline_band

from _data import require

RAW = REPO / "data" / "raw"
OUT = REPO / "charts"
OUT.mkdir(parents=True, exist_ok=True)

# ── 調色盤
#
# 色彩只編碼「實體」，不編碼「排名」或「順序位置」。
# 兩張圖畫的都是同一個實體（Hami Video），所以**不使用類別色相區分**：
#   A：三格全部同一個青藍——三場賽事是同一個品牌的三段時間，不是三個實體。
#   C：同色相的兩個明度階（序數）——週與日是同一份資料的兩種聚合，不是兩件事。
#      深＝日資料（揭露），淺＝週資料（抹平者），明度差本身就在講「粗細」。
# ══════════════════════════════════════════════════════════════════════════
#  視覺方向：**淡青藍紙上的量測報告**（2026-08-09，與姊妹專案 broadband-dashboard
#  同一套結構與中性色，主色不同：這邊青藍、那邊靛藍）。
#  三階明度：紙（#eef4f7）→ 深階帶（#e5eff3）→ 卡（#fafdfe）。
#  **不使用純白**——純白會讓整頁退回「一份 Word 報告」。也不用深色：繁體中文
#  筆畫密度高，淺字在暗底會產生光暈，系統字體沒有為深色調整字重。
#  字體 IBM Plex Sans／Mono ＋ Noto Sans TC，經 Google Fonts 載入，
#  三個堆疊都保留系統字後備，離線開啟自動退回。**預設給桌機觀看。**
# ══════════════════════════════════════════════════════════════════════════
S1 = "#1682a8"                            # 主圖：唯一系列色（三格同一實體）
# 同色相兩個明度階：深＝日資料（揭露者）、淺＝週資料（抹平者）。
C_COARSE, C_FINE = "#a4cbda", "#0e647f"
C_COARSE_FILL = "rgba(164,203,218,0.42)"

PLANE = "#e5e7ee"        # 桌面：與 broadband 共用的中性殼
PAPER = "#eef4f7"        # 紙：淡青藍
PAPER2 = "#e5eff3"       # 深階帶：說明區、統計磚
SURFACE = "#fafdfe"      # 卡片面：近白冷調，不是白
HAIR = "rgba(19,24,34,0.10)"
INK, INK2, MUTED, MUTED2 = "#131822", "#4c5666", "#8b94a3", "#7c8695"
GRID, AXIS = "rgba(19,24,34,0.07)", "rgba(19,24,34,0.15)"
SHADE = "rgba(19,24,34,0.06)"           # 賽程陰影：中性，不佔用類別色
FOOT = "#171b24"
SANS = ("'IBM Plex Sans', 'Noto Sans TC', system-ui, -apple-system, "
        "'Segoe UI', 'Microsoft JhengHei', sans-serif")
MONO = ("'IBM Plex Mono', 'Noto Sans TC', ui-monospace, 'Cascadia Mono', "
        "'SF Mono', Consolas, monospace")
FONT = SANS
FONTS_HREF = ("https://fonts.googleapis.com/css2?"
              "family=IBM+Plex+Sans:wght@400;500;600"
              "&family=IBM+Plex+Mono:wght@400;500;600"
              "&family=Noto+Sans+TC:wght@300;400;500;700&display=swap")
BYLINE = "陳嘉翔　資料工程與分析作品集"
DISCLAIMER = "搜尋熱度 ≠ 訂閱數"

# ── 資料
wk = pd.read_csv(require("groupA_brand_5yr.csv"), index_col=0, parse_dates=True)
wk = wk[~wk["isPartial"].astype(bool)]["Hami Video"]
dy = pd.read_csv(require("res_3mo_worldcup.csv"), index_col=0, parse_dates=True)
dy = dy[~dy["isPartial"].astype(bool)]["Hami Video"]

EVENTS = [
    dict(name="2022 世界盃", peak="2022-11-20", start=dt.date(2022, 11, 20), end=dt.date(2022, 12, 18),
         baseline=1.0, back=5, label="賽程"),
    dict(name="2023 WBC",   peak="2023-03-05", start=dt.date(2023, 3, 8),   end=dt.date(2023, 3, 12),
         baseline=2.0, back=3, label="台灣賽事"),
    dict(name="2024 巴黎奧運", peak="2024-07-28", start=dt.date(2024, 7, 26), end=dt.date(2024, 8, 11),
         baseline=2.0, back=3, label="賽程"),
]
# 賽程長度**由日期推導**，不另外手寫。陰影寬度本來就是用 start/end 畫的
# （WBC 實為 0.571 週），標籤若另存一份 0.6，改了日期只會有一邊跟著動。
for _e in EVENTS:
    _e["dur"] = round((_e["end"] - _e["start"]).days / 7, 1)
    _e["note"] = f"{_e['label']} {_e['dur']} 週"
XLO, DHI, AHI = -3, 12, 8   # XLO~DHI 為收集範圍；AHI 為主圖的顯示上限
# 主圖的版面常數。標註要用像素位移把文字送到指定的資料高度，就必須知道繪圖區高度，
# 抽成常數以免和 update_layout 的 height／margin 各寫一份而漂移。
A_HEIGHT, A_MARGIN_T, A_MARGIN_B = 430, 52, 54
A_PLOT_H = A_HEIGHT - A_MARGIN_T - A_MARGIN_B      # 324px
A_YMAX = 1.14                                       # y 軸上限（0~1.14）


def a_yshift_to(y_from, y_to):
    """求把標註從資料高度 y_from 推到 y_to 所需的像素位移（Plotly 的 ay 正值向下）。"""
    return -round((y_to - y_from) / A_YMAX * A_PLOT_H)

for e in EVENTS:
    pk = pd.Timestamp(e["peak"]); pi = wk.index.get_loc(pk); peak = int(wk.iloc[pi])
    idx = [i for i in range(pi + XLO, pi + DHI + 1) if 0 <= i < len(wk)]
    # 基準帶＝峰值前 26~6 週的 p25–p75（定義與失效點見 metrics.baseline_band 與其測試）。
    blo, bhi = baseline_band(wk, pi)
    e.update(peak_val=peak, pi=pi,
             x=[i - pi for i in idx],
             raw=[int(wk.iloc[i]) for i in idx],
             y=[wk.iloc[i] / peak for i in idx],
             x0=(e["start"] - pk.date()).days / 7,
             x1=(e["end"] - pk.date()).days / 7,
             blo=blo, bhi=bhi, blo_n=blo / peak, bhi_n=bhi / peak)


CSS = f"""
*{{box-sizing:border-box;}}
html{{-webkit-text-size-adjust:100%;}}
body{{margin:0;background:{PAPER};color:{INK};font-family:{SANS};
     line-height:1.72;letter-spacing:.005em;-webkit-font-smoothing:antialiased;}}
.wrap{{max-width:1180px;margin:0 auto;padding:0 56px;}}

.topbar{{background:{PAPER2};border-bottom:1px solid {HAIR};}}
.topbar .wrap{{display:flex;align-items:center;justify-content:space-between;
             height:60px;gap:24px;}}
.brand{{display:flex;align-items:center;gap:11px;min-width:0;}}
.brand .dot{{width:16px;height:16px;border-radius:4px;background:{S1};flex:none;}}
.brand .name{{font-size:13.5px;font-weight:500;}}
.brand .bar{{width:1px;height:14px;background:rgba(19,24,34,.14);margin:0 4px;}}
.brand .who{{font-size:12.5px;color:#6c7686;}}
.tabs{{display:flex;gap:22px;font-family:{MONO};font-size:11px;color:{MUTED};
     white-space:nowrap;}}
.tabs a{{color:{MUTED};border:0;}}
.tabs a:hover{{color:{INK};}}
.tabs .on{{color:{INK};border-bottom:2px solid {S1};padding-bottom:2px;}}

.hero{{background:linear-gradient(180deg,#e4eef2 0%,{PAPER} 56%);
     padding:66px 0 0;}}
.eyebrow{{font-family:{MONO};font-size:10.5px;letter-spacing:.24em;
        text-transform:uppercase;color:{S1};display:block;margin-bottom:18px;
        font-weight:500;}}
h1{{font-size:clamp(2rem,3.6vw,2.9rem);font-weight:600;margin:0 0 22px;
   letter-spacing:-.035em;line-height:1.18;max-width:22ch;text-wrap:balance;}}
h1 em{{font-style:normal;color:{S1};}}
/* 中文可以在任意兩字之間斷行，`text-wrap:balance` 只調每行長度、不認詞界，
   所以標題會斷成「賽事帶來的是脈／衝」。標題切成 nowrap 的語意塊即可。 */
h1 span{{white-space:nowrap;}}
.standfirst{{font-size:16.5px;font-weight:300;color:{INK2};margin:0;max-width:58ch;}}
.standfirst b{{color:{INK};font-weight:500;}}

.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:40px;}}
.stat{{background:{SURFACE};border:1px solid {HAIR};border-radius:12px;
     padding:20px 22px;transition:transform .25s ease,border-color .25s ease;}}
.stat:hover{{transform:translateY(-3px);border-color:rgba(19,24,34,.18);}}
.stat .n{{font-size:13.5px;font-weight:500;margin-bottom:12px;}}
.stat .v{{display:flex;align-items:baseline;gap:8px;}}
.stat .v b{{font-family:{MONO};font-size:34px;font-weight:500;color:{S1};
          letter-spacing:-.04em;}}
.stat .v span{{font-size:13px;color:{MUTED};}}
.stat .meta{{display:flex;gap:18px;margin-top:14px;padding-top:12px;
           border-top:1px solid rgba(19,24,34,.08);font-family:{MONO};
           font-size:11.5px;color:{MUTED};}}
.heronote{{font-size:14px;font-weight:300;color:{INK2};margin:20px 0 0;max-width:82ch;}}
.heronote b{{color:{INK};font-weight:500;}}

.sec{{padding:56px 0 0;}}
h2{{font-size:clamp(1.35rem,2.3vw,1.65rem);font-weight:500;margin:0 0 10px;
   letter-spacing:-.025em;line-height:1.3;}}
h3{{font-size:14.5px;font-weight:500;margin:0 0 12px;padding-bottom:8px;
   border-bottom:1px solid rgba(19,24,34,.16);}}
.sub{{font-size:14.5px;font-weight:300;color:{INK2};margin:0 0 24px;max-width:82ch;}}
.sub b{{color:{INK};font-weight:500;}}

.card{{background:{SURFACE};border:1px solid {HAIR};border-radius:12px;
     padding:14px 12px 6px;overflow-x:auto;}}
.card > div{{min-width:880px;}}

.cols{{display:grid;grid-template-columns:1fr 1fr;gap:40px;padding:44px 0 0;}}
.items{{display:flex;flex-direction:column;gap:12px;}}
.item{{display:flex;gap:14px;}}
.item .i{{font-family:{MONO};font-size:11.5px;color:{S1};font-weight:500;
        padding-top:3px;flex:none;}}
.item .t{{font-size:13.5px;color:{INK2};}}
.item .t b{{color:{INK};font-weight:500;}}
.panel{{background:{PAPER2};border:1px solid rgba(22,130,168,.20);border-radius:12px;
      padding:18px 22px;}}
.panel p{{margin:0;font-size:12.8px;color:{INK2};}}
.panel .crit{{color:#a83a2e;font-weight:500;}}
.pair{{display:flex;align-items:baseline;gap:22px;margin-bottom:12px;}}
.pair .v{{font-family:{MONO};font-size:26px;font-weight:500;letter-spacing:-.03em;}}
.pair .l{{font-size:11.5px;color:{MUTED2};margin-top:3px;}}
.pair .div{{width:1px;align-self:stretch;background:rgba(19,24,34,.12);}}

details{{margin-top:28px;border-top:1px solid {HAIR};padding-top:6px;}}
summary{{cursor:pointer;font-size:12.5px;color:{INK2};padding:8px 0;
       font-family:{MONO};letter-spacing:.02em;}}
summary:hover{{color:{INK};}}
summary:focus-visible{{outline:2px solid {S1};outline-offset:3px;}}
table{{border-collapse:collapse;font-size:12.5px;margin-top:10px;
     font-variant-numeric:tabular-nums;}}
th,td{{padding:9px 16px 9px 0;text-align:right;}}
th:first-child,td:first-child{{text-align:left;}}
th{{color:#98a0ad;font-weight:500;font-family:{MONO};font-size:10px;
   letter-spacing:.14em;text-transform:uppercase;
   border-bottom:1px solid rgba(19,24,34,.22);}}
td{{border-bottom:1px solid rgba(19,24,34,.08);color:{INK2};}}
td:first-child{{color:{INK};}}
tbody tr:hover,tr:hover{{background:rgba(19,24,34,.035);}}
code{{font-family:{MONO};font-size:12px;background:rgba(19,24,34,.06);
    padding:2px 6px;border-radius:4px;color:{INK2};}}

.foot{{background:{FOOT};color:rgba(236,239,244,.62);margin-top:56px;padding:36px 0;
     font-family:{MONO};font-size:11.5px;line-height:1.95;}}
.foot code{{background:rgba(255,255,255,.09);color:#c3cbd6;}}
.small{{font-size:12.5px;color:{MUTED};line-height:1.85;max-width:88ch;
      margin:20px 0 0;}}
.small b{{color:{INK2};font-weight:500;}}

a{{color:{S1};text-decoration:none;border-bottom:1px solid rgba(22,130,168,.28);}}
a:hover{{color:#0e647f;border-bottom-color:#0e647f;}}
.reveal{{opacity:0;transform:translateY(14px);}}
.reveal.in{{opacity:1;transform:none;
          transition:opacity .7s cubic-bezier(.2,.7,.2,1),
                     transform .7s cubic-bezier(.2,.7,.2,1);}}
@media (prefers-reduced-motion: reduce){{
  .reveal,.reveal.in{{opacity:1;transform:none;transition:none;}}
}}
@media (max-width:1080px){{
  .wrap{{padding:0 28px;}}
  .stats{{grid-template-columns:1fr;}}
  .cols{{grid-template-columns:1fr;gap:28px;}}
  .hero{{padding-top:46px;}}
}}
"""


def shell(title, h1, eyebrow, standfirst, extra_top, figdiv, table_html,
          tab, extra="", more=""):
    """圖表頁的外殼。

    門面只留讀者做判斷需要的東西；把方法細節塞進圖下方的六行小字，
    對讀者是雜訊，對自己才是紀錄——所以收進可摺疊區，兩者都不犧牲。
    """
    more_html = (f'<details><summary>方法細節（座標語意、基準帶定義）</summary>'
                 f'<p class="small">{more}</p></details>') if more else ""
    t1 = ' class="on"' if tab == 1 else ""
    t2 = ' class="on"' if tab == 2 else ""
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS_HREF}" rel="stylesheet">
<style>{CSS}</style>

<header class="topbar"><div class="wrap">
  <div class="brand">
    <span class="dot"></span>
    <span class="name">Hami Video 賽事熱度衰退</span>
    <span class="bar"></span>
    <span class="who">{BYLINE}</span>
  </div>
  <nav class="tabs">
    <a href="decay-by-event.html"{t1}>三格衰退主圖</a>
    <a href="daily-vs-weekly.html"{t2}>日 vs 週對照</a>
  </nav>
</div></header>

<section class="hero"><div class="wrap">
  <span class="eyebrow">{eyebrow}</span>
  <h1>{h1}</h1>
  <p class="standfirst">{standfirst}</p>
  {extra_top}
</div></section>

<main>
<section class="sec reveal"><div class="wrap">
  <div class="card">{figdiv}</div>
  <details><summary>表格檢視（每個數值都可讀，不倚賴 tooltip）</summary>{table_html}</details>
  <p class="small">{extra}</p>{more_html}
</div></section>
</main>

<footer class="foot"><div class="wrap">
圖表由 <code>scripts/make_charts.py</code> 產生；
判準於檢視資料前存檔，事後修正一律標示為事後。<br>
外部求職者以公開資料製作，非中華電信內部文件，不代表該公司立場。
</div></footer>

<script>
(() => {{
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {{
    document.querySelectorAll('.reveal').forEach(el => el.classList.add('in'));
    return;
  }}
  const io = new IntersectionObserver((es) => {{
    es.forEach(e => {{ if (e.isIntersecting) {{
      e.target.classList.add('in'); io.unobserve(e.target);
    }} }});
  }}, {{threshold: 0.06, rootMargin: '0px 0px -6% 0px'}});
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
}})();
</script>"""


BASE_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                   font=dict(family=FONT, size=12.5, color=INK2),
                   margin=dict(l=54, r=24, t=52, b=54), hovermode="x unified")

# ══════════════════════════════ A：三格 small multiples ══════════════════════════════
figA = make_subplots(rows=1, cols=3, shared_yaxes=True, horizontal_spacing=0.045,
                     subplot_titles=[f"{e['name']}　·　{e['note']}" for e in EVENTS])
for c, e in enumerate(EVENTS, start=1):
    # ⚠️ trace 必須先加：add_vrect/add_hrect/add_hline 的 exclude_empty_subplots 預設為 True，
    # 對「還沒有 trace 的 subplot」會靜默丟棄該 shape（實測：先 shape 後 trace → shapes=0）。
    figA.add_trace(go.Scatter(
        x=e["x"], y=e["y"], mode="lines+markers", name=e["name"],
        line=dict(color=S1, width=2), marker=dict(size=8, color=S1,
                                                  line=dict(color=SURFACE, width=2)),
        customdata=e["raw"], showlegend=False,
        hovertemplate="峰值後第 %{x} 週<br>指數 %{customdata}（峰值的 %{y:.1%}）<extra></extra>"),
        row=1, col=c)
    figA.add_vrect(x0=e["x0"], x1=e["x1"], row=1, col=c,
                   fillcolor=SHADE, line_width=0, layer="below")
    figA.add_hrect(y0=e["blo_n"], y1=e["bhi_n"], row=1, col=c,
                   fillcolor="rgba(19,24,34,0.09)", line_width=0, layer="below")
    figA.add_hline(y=e["bhi_n"], row=1, col=c, line=dict(color=AXIS, width=1.5))
    xr = f"x{c if c > 1 else ''}"; yr = f"y{c if c > 1 else ''}"
    figA.add_annotation(x=0, y=1.0, xref=xr, yref=yr, text=f"<b>峰值 {e['peak_val']}</b>",
                        showarrow=False, yshift=17,
                        font=dict(size=12, color=INK, family=MONO))
    # 基準帶標籤放右上，疊在免責小字下面一行。
    # 原位置（貼在帶的右端 y=bhi_n）同時被賽後的平緩資料線與「N 週後回到基準」的引線穿過。
    # 三格真正共通的空白只有右上：峰值在 x=0，之後單調下降。
    figA.add_annotation(x=AHI - 0.2, y=0.87, xref=xr, yref=yr,
                        text=f"賽前基準帶 {e['blo']:.0f}–{e['bhi']:.0f}", showarrow=False,
                        xanchor="right", font=dict(size=11.5, color=MUTED, family=MONO))
    # ay 為算出來的值（把文字抬到資料高度 0.38），xanchor=left（文字向右展開）。
    # 向右展開是關鍵——**陡降段永遠在回歸點的左側**，右側必為已回到基準的平緩段，
    # 所以這個方向對三格都成立，不必逐格微調。
    y_back = e["y"][e["back"] - XLO]
    figA.add_annotation(x=e["back"], y=y_back, xref=xr, yref=yr,
                        text=f"<b>{e['back']} 週後回到基準</b>", showarrow=True, arrowhead=0,
                        arrowcolor=MUTED, arrowwidth=1, ax=10, ay=a_yshift_to(y_back, 0.38),
                        xanchor="left", font=dict(size=11.5, color=INK2, family=FONT))
    # 免責小字放右上角：三格的右上都是空白（峰值在 x=0，之後單調下降到基準）。
    # 原本放左上會被 x=-1→0 的陡升段穿過；2026-08-08 實際渲染截圖才看見。
    figA.add_annotation(x=AHI - 0.2, y=0.97, xref=xr, yref=yr, text=DISCLAIMER,
                        showarrow=False, xanchor="right",
                        font=dict(size=11, color=MUTED, family=MONO))
figA.update_xaxes(range=[XLO - .35, AHI + .35], dtick=2, title_text="峰值後週數",
                  showgrid=False, zeroline=False, linecolor=AXIS, ticks="outside",
                  tickcolor=AXIS, ticklen=4,
                  tickfont=dict(size=11, color=MUTED, family=MONO))
figA.update_yaxes(range=[0, 1.14], tickformat=".0%", showgrid=True, gridcolor=GRID,
                  gridwidth=1, zeroline=False, linecolor=AXIS,
                  tickfont=dict(size=11, color=MUTED, family=MONO))
# 縱軸標題已移除（旋轉中文不易讀）。改放進圖上方的說明文字。
figA.update_layout(height=430, **BASE_LAYOUT)
for a in figA.layout.annotations[:3]:
    a.font = dict(size=13.5, color=INK, family=FONT)

def assert_shapes(fig, label, expect):
    """規格層斷言：shape 被靜默丟棄過一次（exclude_empty_subplots），不能再靠人工發現。"""
    got = len(fig.layout.shapes)
    kinds = [s.type for s in fig.layout.shapes]
    assert got == expect, f"[{label}] shapes 應有 {expect} 個，實際 {got} 個：{kinds}"
    for i, s in enumerate(fig.layout.shapes):
        assert s.fillcolor or (s.line and s.line.color), f"[{label}] shape#{i} 既無填色也無線色"
    print(f"  ✔ {label}: shapes={got} {kinds}")


def assert_ann_inside(fig, label, yranges):
    """幾何斷言：資料座標的標註必須整個落在繪圖區內。"""
    lay = fig.layout
    plot_h = lay.height - lay.margin.t - lay.margin.b
    bad = []
    for a in lay.annotations:
        yr = str(a.yref or "y")
        if yr.startswith("paper") or not isinstance(a.y, (int, float)):
            continue
        lo, hi = yranges[yr]
        px = (a.y - lo) / (hi - lo) * plot_h + (a.yshift or 0)
        half = (a.font.size or 12) / 2 + 1.5
        if a.yanchor in (None, "auto", "middle"):
            top, bot = px + half, px - half
        elif a.yanchor == "bottom":
            top, bot = px + 2 * half, px
        else:
            top, bot = px, px - 2 * half
        if bot < 0 or top > plot_h:
            bad.append(f"「{a.text}」 {yr} y={a.y:.4f} → {bot:.1f}~{top:.1f}px（繪圖區 0~{plot_h:.0f}）")
    assert not bad, f"[{label}] 標註超出繪圖區：\n    " + "\n    ".join(bad)
    print(f"  ✔ {label}: 標註全數落在繪圖區內（繪圖區高 {plot_h:.0f}px）")


print("斷言檢查：")
# A：每格 = 賽程 vrect + 基準帶 hrect + 基準上緣 hline，共 3 × 3 格 = 9
assert_shapes(figA, "decay-by-event", 9)
assert_ann_inside(figA, "decay-by-event", {f"y{i or ''}": (0, 1.14) for i in range(0, 4)})


def after_vals(e, n=3):
    return " , ".join(str(e["raw"][e["x"].index(e["back"] + k)]) for k in range(n)
                      if (e["back"] + k) in e["x"])

rowsA = "".join(
    f"<tr><td>{e['name']}</td><td>{e['peak_val']}</td><td>{e['dur']}</td>"
    f"<td>{e['baseline']:.0f}</td><td>{e['back']}</td><td>{after_vals(e)}</td></tr>"
    for e in EVENTS)
tableA = ("<table><tr><th>賽事</th><th>峰值指數</th><th>賽程(週)</th><th>賽前基準</th>"
          f"<th>回到基準(週)</th><th>回歸後三週的值</th></tr>{rowsA}</table>")

# hero 下方的三張讀數卡：把「三場皆然」這個結論放進版面，而不是只寫在句子裡。
statsA = '<div class="stats">' + "".join(
    f"""<div class="stat">
      <div class="n">{e['name']}</div>
      <div class="v"><b>{e['back']}</b><span>週後回到基準</span></div>
      <div class="meta"><span>賽程 {e['dur']} 週</span><span>峰值 {e['peak_val']}</span>
        <span>基準 {e['blo']:.0f}–{e['bhi']:.0f}</span></div>
    </div>""" for e in EVENTS) + "</div>"

backs = sorted({e["back"] for e in EVENTS})
durs = sorted({e["dur"] for e in EVENTS})

# ══════════════════════════════ C：世足 日 vs 週（方法論） ══════════════════════════════
d0, d1 = pd.Timestamp("2022-11-01"), pd.Timestamp("2023-01-31")
dsub = dy[(dy.index >= d0) & (dy.index <= d1)]
wsub = wk[(wk.index >= d0) & (wk.index <= d1)]
dn, wn = dsub / dsub.max(), wsub / wsub.max()

figC = go.Figure()
figC.add_trace(go.Scatter(x=wn.index, y=wn.values, mode="lines", name="週資料（5 年查詢）",
                          line=dict(color=C_COARSE, width=2, shape="hv"), fill="tozeroy",
                          fillcolor=C_COARSE_FILL, customdata=wsub.values,
                          hovertemplate="週起 %{x|%m/%d}<br>週指數 %{customdata}"
                                        "（該窗峰值的 %{y:.1%}）<extra></extra>"))
figC.add_trace(go.Scatter(x=dn.index, y=dn.values, mode="lines", name="日資料（3 個月查詢）",
                          line=dict(color=C_FINE, width=2), customdata=dsub.values,
                          hovertemplate="%{x|%m/%d}<br>日指數 %{customdata}"
                                        "（該窗峰值的 %{y:.1%}）<extra></extra>"))
figC.add_annotation(x=pd.Timestamp("2022-12-18"), y=1.0, text="<b>決賽日 12/18　日指數 61</b><br>"
                    "同一週的週指數只有 9　<b>被壓掉 6.8 倍</b>",
                    showarrow=True, arrowhead=0, arrowcolor=MUTED, arrowwidth=1,
                    ax=-96, ay=-46, font=dict(size=12, color=INK, family=FONT), align="left")
# ax=−132：原位置讓文字騎在 11/20 的陡升段上。往左推到 11/20 之前的平坦區。
figC.add_annotation(x=pd.Timestamp("2022-11-20"), y=0.62, text="週資料的峰值在<b>開幕週</b>",
                    showarrow=True, arrowhead=0, arrowcolor=MUTED, arrowwidth=1,
                    ax=-132, ay=-30, font=dict(size=12, color=INK2, family=FONT), align="left")
figC.add_annotation(x=pd.Timestamp("2022-11-03"), y=1.06, text=DISCLAIMER, showarrow=False,
                    xanchor="left", font=dict(size=11, color=MUTED, family=MONO))
# range 明確寫出（原本靠 autorange）：Plotly 不會把 autorange 的結果寫進 layout JSON，
# 驗證器就無從把資料座標換算成像素，標註 vs 資料線的檢查會整段跳過。
figC.update_xaxes(range=[d0, d1],
                  showgrid=False, zeroline=False, linecolor=AXIS, ticks="outside",
                  tickcolor=AXIS, ticklen=4, tickformat="%m/%d",
                  tickfont=dict(size=11, color=MUTED, family=MONO))
figC.update_yaxes(range=[0, 1.15], tickformat=".0%",   # 縱軸標題已移除，理由同主圖
                  showgrid=True, gridcolor=GRID, zeroline=False, linecolor=AXIS,
                  tickfont=dict(size=11, color=MUTED, family=MONO))
figC.update_layout(height=430,
                   legend=dict(orientation="h", y=1.13, x=0,
                               font=dict(size=12.5, family=FONT)),
                   **BASE_LAYOUT)

pick = ["2022-11-20", "2022-11-24", "2022-12-11", "2022-12-18", "2022-12-19", "2022-12-25"]
rowsC = "".join(
    f"<tr><td>{p}</td><td>{int(dsub.loc[pd.Timestamp(p)]) if pd.Timestamp(p) in dsub.index else '—'}</td>"
    f"<td>{int(wsub.loc[pd.Timestamp(p)]) if pd.Timestamp(p) in wsub.index else '—'}</td></tr>"
    for p in pick)
tableC = f"<table><tr><th>日期</th><th>日指數</th><th>該日所屬週的週指數</th></tr>{rowsC}</table>"

statsC = """<div class="stats" style="grid-template-columns:repeat(3,1fr);">
  <div class="stat"><div class="n">決賽日 12/18 的日指數</div>
    <div class="v"><b>61</b><span>日解析度</span></div></div>
  <div class="stat"><div class="n">同一週的週指數</div>
    <div class="v"><b style="color:#79aec1">9</b><span>週解析度</span></div></div>
  <div class="stat"><div class="n">被週聚合壓掉的倍率</div>
    <div class="v"><b style="color:#131822">6.8×</b><span>同一週內</span></div></div>
</div>"""

# ── 輸出
# responsive: True 是手機掃 QR 進來的必要條件。
opts = dict(full_html=False, include_plotlyjs="directory",
            config={"displayModeBar": False, "responsive": True})

(OUT / "decay-by-event.html").write_text(shell(
    "三場賽事的熱度回歸｜Hami Video 搜尋熱度",
    "<span>賽事帶來的是<em>脈衝</em>，</span><span>不是<em>階梯</em>。</span>",
    f"Google Trends 台灣　·　週解析度　·　{wk.index[0]:%Y-%m} — {wk.index[-1]:%Y-%m}",
    "賽事熱度在賽後 1–2 週內完全回到賽前基準，三場皆然。"
    "在這份資料的解析度下，觀測不到任何殘留提升。",
    statsA + f'<p class="heronote"><b>結論不依賴任何單一數字</b>，'
             f'而在於三場賽事的賽程長度介於 {min(durs)} 至 {max(durs)} 週，'
             f'回歸結果仍然一致。衰退<b>形狀</b>的差異，'
             f'幾乎可完全歸因於賽程長度的機械效果。</p>'
             '<h2 style="margin-top:52px;">三格重複同一個結構，讓讀者自己看出模式一致</h2>'
             '<p class="sub"><b>直式陰影是實際賽程長度</b>（4.0／0.6／2.3 週，等比），'
             '<b>橫向灰帶是賽前基準帶</b>，帶上緣的實線是回歸門檻。'
             '縱軸為各場相對於自身峰值的比例（＝100%），三格不共用絕對尺度。'
             '三格採用同一顏色，因三場屬同一品牌的不同時間區段，而非三個獨立實體。</p>',
    figA.to_html(**opts), tableA, tab=1,
    # 門面：讀者要對這張圖下判斷，只需要這三件事。
    extra="<b>限制</b>：搜尋熱度不等於訂閱數，賽後停止搜尋者未必退訂，本資料無法區分兩者。"
    "<br>賽後基準區的值為 1–3 的整數，<b>偵測下限依基準而異</b>："
    "基準 3 需 +33%、基準 2 需 +50%、<b>基準 1（世足）需 +100%</b>；"
    "低於該幅度的殘留提升，本資料無法偵測。"
    "<br><b>三場賽事 Hami Video 均有轉播</b>（世足專區與獨家 AR／WBC 60 天方案與 Hami WBC1 台／"
    "巴黎奧運官方轉播表，2026-08-06 查證），選此三場係因其為 Hami Video 自身經歷的賽事。"
    "<b>惟賽事日期本身未查一手來源</b>，峰值與賽事的對應係日期對齊，而非經驗證的歸因。"
    "<br><b>資料</b>：Google Trends 台灣，Hami Video，週解析度，2021-08 至 2026-07"
    "（<code>data/raw/groupA_brand_5yr.csv</code>，取於 2026-08-03）。",
    # 摺疊：寫給自己與願意深讀的人。
    more="<b>基準帶定義</b>：峰值前 26～6 週的 p25–p75。"
    "採用分位數而非 min–max，因 WBC 的基準窗含世足（max=36），min–max 會被前一事件污染。"
    "帶上緣（p75）同時是「回到基準」的判定門檻。"
    "<b>奧運賽前第 1 週的值 13 落在帶外，屬賽前預熱，本來就應可見。</b>"
    "<br><b>座標語意</b>：資料點為<b>整週聚合、標於週起始日</b>；直式陰影為<b>實際賽程日期</b>。"
    "兩者不是同一種座標，因此短賽事會出現「峰值點落在陰影左側」："
    "WBC 的峰值週自 3/5 起算，台灣賽事 3/8 才開打。這是資料本身的粒度，不是繪圖誤差。"
), encoding="utf-8")

(OUT / "daily-vs-weekly.html").write_text(shell(
    "日資料與週資料講出不同的故事｜解析度如何改變結論",
    "<span>日資料與週資料</span><span>講出不同的故事</span>",
    "方法論　·　2022 世界盃",
    "週平均將單日爆發抹平。<b>日資料的最高點落在決賽日 12/18，"
    "週資料的最高點卻落在開幕週</b>；解析度的選擇會改變結論。",
    statsC,
    figC.to_html(**opts), tableC, tab=2,
    extra="<b>兩條線怎麼讀</b>：兩條線<b>各自相對於自己的峰值</b>（＝100%）。"
    "採同色相的深淺兩階，因兩者為同一份資料的兩種聚合方式而非兩個實體；"
    "深階為日資料，淺階為週資料。<br>"
    "<b>不可以這樣讀</b>：兩條線來自<b>兩次獨立查詢</b>（日為 3 個月窗、週為 5 年窗），"
    "各自正規化，因此僅可比較形狀與峰值位置，<b>不可比較高度</b>。"
    "「被壓掉 6.8 倍」係同一週內日指數 61 對週指數 9 的落差，"
    "為兩種聚合方式的差異，而非兩個尺度直接相除。<br>"
    "搜尋熱度不等於訂閱數；賽事日期未查一手來源。"
), encoding="utf-8")

print("已產生：")
for p in sorted(OUT.iterdir()):
    print(f"  {p.name}  {p.stat().st_size:,} bytes")
