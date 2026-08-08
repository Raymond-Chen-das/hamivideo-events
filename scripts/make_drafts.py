# -*- coding: utf-8 -*-
"""產生三張視覺草稿（HTML + Plotly）。零 API 請求，只讀 raw/ 既有 CSV。
A：三格 small multiples（主視覺候選）
B：疊合正規化曲線（對照，不進交付）
C：世足 日 vs 週（方法論，第二張）
"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import warnings, datetime as dt
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

RAW = REPO / "data" / "raw"
OUT = REPO / "drafts"
OUT.mkdir(parents=True, exist_ok=True)

# ── 調色盤（dataviz 參考實例，已跑 validate_palette.js：全 PASS，aqua 對比 WARN → 直接標籤＋表格檢視作為 relief）
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SHADE = "rgba(11,11,11,0.055)"          # 賽程陰影：中性，不佔用類別色
FONT = 'system-ui, -apple-system, "Segoe UI", "Microsoft JhengHei", sans-serif'
DISCLAIMER = "搜尋熱度 ≠ 訂閱數"

# ── 資料
wk = pd.read_csv(RAW / "groupA_brand_5yr.csv", index_col=0, parse_dates=True)
wk = wk[~wk["isPartial"].astype(bool)]["Hami Video"]
dy = pd.read_csv(RAW / "res_3mo_worldcup.csv", index_col=0, parse_dates=True)
dy = dy[~dy["isPartial"].astype(bool)]["Hami Video"]

EVENTS = [
    dict(name="2022 世界盃", peak="2022-11-20", start=dt.date(2022, 11, 20), end=dt.date(2022, 12, 18),
         baseline=1.0, back=5, dur=4.0, note="賽程 4.0 週"),
    dict(name="2023 WBC",   peak="2023-03-05", start=dt.date(2023, 3, 8),   end=dt.date(2023, 3, 12),
         baseline=2.0, back=3, dur=0.6, note="台灣賽事 0.6 週"),
    dict(name="2024 巴黎奧運", peak="2024-07-28", start=dt.date(2024, 7, 26), end=dt.date(2024, 8, 11),
         baseline=2.0, back=3, dur=2.3, note="賽程 2.3 週"),
]
XLO, DHI, AHI = -3, 12, 8   # XLO~DHI 為收集範圍；AHI 為草稿 A 的顯示上限

for e in EVENTS:
    pk = pd.Timestamp(e["peak"]); pi = wk.index.get_loc(pk); peak = int(wk.iloc[pi])
    idx = [i for i in range(pi + XLO, pi + DHI + 1) if 0 <= i < len(wk)]
    # 基準帶＝峰值前 26~6 週的 p25–p75。用分位數而非 min–max：WBC 的基準窗含世足（max=36），
    # min–max 會被前一事件污染成無意義的寬帶。p75 同時是回歸門檻。
    w20 = wk.iloc[max(0, pi - 26): pi - 5]
    blo, bhi = float(w20.quantile(.25)), float(w20.quantile(.75))
    e.update(peak_val=peak, pi=pi,
             x=[i - pi for i in idx],
             raw=[int(wk.iloc[i]) for i in idx],
             y=[wk.iloc[i] / peak for i in idx],
             x0=(e["start"] - pk.date()).days / 7,
             x1=(e["end"] - pk.date()).days / 7,
             blo=blo, bhi=bhi, blo_n=blo / peak, bhi_n=bhi / peak)


def shell(title, sub, figdiv, table_html, extra=""):
    return f"""<meta charset="utf-8"><title>{title}</title>
<style>
 body{{margin:0;background:#f9f9f7;color:{INK};font-family:{FONT};}}
 .wrap{{max-width:1180px;margin:0 auto;padding:32px 20px 64px;}}
 h1{{font-size:21px;font-weight:650;margin:0 0 6px;letter-spacing:-.01em;}}
 .sub{{font-size:13.5px;color:{INK2};margin:0 0 22px;line-height:1.65;}}
 .card{{background:{SURFACE};border:1px solid rgba(11,11,11,.10);border-radius:10px;padding:8px 6px 4px;}}
 details{{margin-top:22px;}} summary{{cursor:pointer;font-size:13px;color:{INK2};padding:6px 0;}}
 table{{border-collapse:collapse;font-size:12.5px;margin-top:10px;font-variant-numeric:tabular-nums;}}
 th,td{{border-bottom:1px solid {GRID};padding:5px 12px 5px 0;text-align:right;}}
 th:first-child,td:first-child{{text-align:left;}} th{{color:{MUTED};font-weight:550;}}
 .foot{{font-size:12px;color:{MUTED};margin-top:20px;line-height:1.7;}}
 .foot b{{color:{INK2};font-weight:600;}}
</style>
<div class="wrap"><h1>{title}</h1><p class="sub">{sub}</p>
<div class="card">{figdiv}</div>
<details><summary>表格檢視（每個數值都可讀，不倚賴 tooltip）</summary>{table_html}</details>
<p class="foot">{extra}</p></div>"""


BASE_LAYOUT = dict(paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
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
                   fillcolor="rgba(11,11,11,0.10)", line_width=0, layer="below")
    figA.add_hline(y=e["bhi_n"], row=1, col=c, line=dict(color=AXIS, width=1.5))
    xr = f"x{c if c > 1 else ''}"; yr = f"y{c if c > 1 else ''}"
    figA.add_annotation(x=0, y=1.0, xref=xr, yref=yr, text=f"<b>峰值 {e['peak_val']}</b>",
                        showarrow=False, yshift=17, font=dict(size=12, color=INK))
    # yshift 必須為正：帶的位置貼近繪圖區底部（距底僅 ~16px），往下放會有半個字高落到軸外。
    figA.add_annotation(x=AHI - 0.2, y=e["bhi_n"], xref=xr, yref=yr,
                        text=f"賽前基準帶 {e['blo']:.0f}–{e['bhi']:.0f}", showarrow=False,
                        yshift=13, xanchor="right", font=dict(size=11.5, color=MUTED))
    # 「陰影＝賽程期間」註記已移除：與「峰值 NN」垂直僅差 1.4px，900px 容器下必然重疊；
    # 且每格標題已寫「賽程 X 週」，陰影就在該位置，註記是冗餘的。
    figA.add_annotation(x=e["back"], y=e["y"][e["back"] - XLO], xref=xr, yref=yr,
                        text=f"<b>{e['back']} 週後回到基準</b>", showarrow=True, arrowhead=0,
                        arrowcolor=MUTED, arrowwidth=1, ax=6, ay=-40,
                        font=dict(size=11.5, color=INK2))
    figA.add_annotation(x=XLO + 0.15, y=0.845, xref=xr, yref=yr, text=DISCLAIMER,
                        showarrow=False, xanchor="left", font=dict(size=11, color=MUTED))
figA.update_xaxes(range=[XLO - .35, AHI + .35], dtick=2, title_text="峰值後週數",
                  showgrid=False, zeroline=False, linecolor=AXIS, ticks="outside",
                  tickcolor=AXIS, ticklen=4, tickfont=dict(size=11.5, color=MUTED))
figA.update_yaxes(range=[0, 1.14], tickformat=".0%", showgrid=True, gridcolor=GRID,
                  gridwidth=1, zeroline=False, linecolor=AXIS,
                  tickfont=dict(size=11.5, color=MUTED))
figA.update_yaxes(title_text="相對於該場峰值", row=1, col=1)
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
    """幾何斷言：資料座標的標註必須整個落在繪圖區內。
    （漏掉這一類，就會發生「賽前基準帶」壓在繪圖區底緣、半個字高落到軸外。）"""
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
assert_shapes(figA, "draft-A", 9)
assert_ann_inside(figA, "draft-A", {f"y{i or ''}": (0, 1.14) for i in range(0, 4)})


def after_vals(e, n=3):
    return " , ".join(str(e["raw"][e["x"].index(e["back"] + k)]) for k in range(n)
                      if (e["back"] + k) in e["x"])

rowsA = "".join(
    f"<tr><td>{e['name']}</td><td>{e['peak_val']}</td><td>{e['dur']}</td>"
    f"<td>{e['baseline']:.0f}</td><td>{e['back']}</td><td>{after_vals(e)}</td></tr>"
    for e in EVENTS)
tableA = ("<table><tr><th>賽事</th><th>峰值指數</th><th>賽程(週)</th><th>賽前基準</th>"
          f"<th>回到基準(週)</th><th>回歸後三週的值</th></tr>{rowsA}</table>")

# ══════════════════════════════ B：疊合正規化曲線（對照） ══════════════════════════════
figB = go.Figure()
for e, col in zip(EVENTS, [S1, S2, S3]):
    xs = [x for x in e["x"] if 0 <= x <= 12]
    ys = [e["y"][e["x"].index(x)] for x in xs]
    figB.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=e["name"],
                              line=dict(color=col, width=2),
                              marker=dict(size=8, color=col, line=dict(color=SURFACE, width=2)),
                              hovertemplate="%{fullData.name}<br>第 %{x} 週：峰值的 %{y:.1%}<extra></extra>"))
    figB.add_annotation(x=xs[-1], y=ys[-1], text=e["name"], showarrow=False, xanchor="left",
                        xshift=8, font=dict(size=11.5, color=INK2))
figB.add_vrect(x0=3, x1=12, fillcolor=SHADE, line_width=0, layer="below")
figB.add_annotation(x=7.5, y=.55, text="第 3 週後三條全部壓在 5.6%–6.5%<br>七成畫布零資訊",
                    showarrow=False, font=dict(size=12, color=MUTED))
figB.update_xaxes(range=[-.4, 15], dtick=2, title_text="峰值後週數", showgrid=False,
                  zeroline=False, linecolor=AXIS, ticks="outside", tickcolor=AXIS,
                  ticklen=4, tickfont=dict(size=11.5, color=MUTED))
figB.update_yaxes(range=[0, 1.08], tickformat=".0%", title_text="相對於該場峰值",
                  showgrid=True, gridcolor=GRID, zeroline=False, linecolor=AXIS,
                  tickfont=dict(size=11.5, color=MUTED))
figB.update_layout(height=430, legend=dict(orientation="h", y=1.1, x=0,
                   font=dict(size=12)), **BASE_LAYOUT)

assert_shapes(figB, "draft-B", 1)   # 第 3 週後的灰底區塊

hdrB = "".join(f"<th>{e['name']}</th>" for e in EVENTS)
rowsB = "".join(
    "<tr><td>第 %d 週</td>" % w +
    "".join(f"<td>{e['y'][e['x'].index(w)]:.3f}</td>" for e in EVENTS) + "</tr>"
    for w in range(0, 13))
tableB = f"<table><tr><th>峰值後</th>{hdrB}</tr>{rowsB}</table>"

# ══════════════════════════════ C：世足 日 vs 週（方法論） ══════════════════════════════
d0, d1 = pd.Timestamp("2022-11-01"), pd.Timestamp("2023-01-31")
dsub = dy[(dy.index >= d0) & (dy.index <= d1)]
wsub = wk[(wk.index >= d0) & (wk.index <= d1)]
dn, wn = dsub / dsub.max(), wsub / wsub.max()

figC = go.Figure()
figC.add_trace(go.Scatter(x=wn.index, y=wn.values, mode="lines", name="週資料（5 年查詢）",
                          line=dict(color=S2, width=2, shape="hv"), fill="tozeroy",
                          fillcolor="rgba(235,104,52,0.10)", customdata=wsub.values,
                          hovertemplate="週起 %{x|%m/%d}<br>週指數 %{customdata}"
                                        "（該窗峰值的 %{y:.1%}）<extra></extra>"))
figC.add_trace(go.Scatter(x=dn.index, y=dn.values, mode="lines", name="日資料（3 個月查詢）",
                          line=dict(color=S1, width=2), customdata=dsub.values,
                          hovertemplate="%{x|%m/%d}<br>日指數 %{customdata}"
                                        "（該窗峰值的 %{y:.1%}）<extra></extra>"))
figC.add_annotation(x=pd.Timestamp("2022-12-18"), y=1.0, text="<b>決賽日 12/18　日指數 61</b><br>"
                    "同一週的週指數只有 9　<b>被壓掉 6.8 倍</b>",
                    showarrow=True, arrowhead=0, arrowcolor=MUTED, arrowwidth=1,
                    ax=-96, ay=-46, font=dict(size=12, color=INK), align="left")
figC.add_annotation(x=pd.Timestamp("2022-11-20"), y=0.62, text="週資料的峰值在<b>開幕週</b>",
                    showarrow=True, arrowhead=0, arrowcolor=MUTED, arrowwidth=1,
                    ax=-4, ay=-52, font=dict(size=12, color=INK2), align="left")
figC.add_annotation(x=pd.Timestamp("2022-11-03"), y=1.06, text=DISCLAIMER, showarrow=False,
                    xanchor="left", font=dict(size=11, color=MUTED))
figC.update_xaxes(showgrid=False, zeroline=False, linecolor=AXIS, ticks="outside",
                  tickcolor=AXIS, ticklen=4, tickformat="%m/%d",
                  tickfont=dict(size=11.5, color=MUTED))
figC.update_yaxes(range=[0, 1.15], tickformat=".0%", title_text="各自相對於自己的峰值",
                  showgrid=True, gridcolor=GRID, zeroline=False, linecolor=AXIS,
                  tickfont=dict(size=11.5, color=MUTED))
figC.update_layout(height=440, legend=dict(orientation="h", y=1.13, x=0, font=dict(size=12)),
                   **BASE_LAYOUT)

pick = ["2022-11-20", "2022-11-24", "2022-12-11", "2022-12-18", "2022-12-19", "2022-12-25"]
rowsC = "".join(
    f"<tr><td>{p}</td><td>{int(dsub.loc[pd.Timestamp(p)]) if pd.Timestamp(p) in dsub.index else '—'}</td>"
    f"<td>{int(wsub.loc[pd.Timestamp(p)]) if pd.Timestamp(p) in wsub.index else '—'}</td></tr>"
    for p in pick)
tableC = f"<table><tr><th>日期</th><th>日指數</th><th>該日所屬週的週指數</th></tr>{rowsC}</table>"

# ── 輸出
opts = dict(full_html=False, include_plotlyjs="directory", config={"displayModeBar": False})
(OUT / "draft-a-small-multiples.html").write_text(shell(
    "草稿 A｜三場賽事的熱度回歸（主視覺候選）",
    "每格一場賽事。<b>直式陰影＝實際賽程長度</b>（4.0／0.6／2.3 週，等比），"
    "<b>橫向灰帶＝賽前基準帶</b>，帶上緣的實線是回歸門檻。三格重複同一結構——讀者自己看出模式一致。",
    figA.to_html(**opts), tableA,
    "<b>資料</b>：Google Trends 台灣，Hami Video，週解析度，2021-08～2026-07（<code>raw/groupA_brand_5yr.csv</code>，"
    "取於 2026-08-03）。<br><b>基準帶定義</b>：峰值前 26～6 週的 p25–p75。"
    "用分位數而非 min–max，因為 WBC 的基準窗含世足（max=36），min–max 會被前一事件污染。"
    "帶上緣（p75）同時是「回到基準」的判定門檻。"
    "<b>奧運賽前第 1 週的值 13 落在帶外——那是賽前預熱，本來就該看得見。</b>"
    "<br><b>座標語意</b>：資料點是<b>整週聚合、標於週起始日</b>；直式陰影是<b>實際賽程日期</b>。"
    "兩者不是同一種座標，所以短賽事會出現「峰值點落在陰影左側」——"
    "WBC 的峰值週從 3/5 起算，台灣賽事 3/8 才開打。這是資料本身的粒度，不是繪圖誤差。"
    "<br><b>限制</b>：搜尋熱度不等於訂閱數——賽後不再搜尋的人未必退訂，"
    "這份資料分不開兩者。<br>賽後基準區的值是 1–3 的整數，"
    "偵測下限依基準而異：基準 3→+33%、基準 2→+50%、<b>基準 1（世足）→+100%</b>；"
    "小於該幅度的殘留提升看不見。<br>賽事日期未查一手來源，屬待驗事實。"
), encoding="utf-8")

(OUT / "draft-b-overlay.html").write_text(shell(
    "草稿 B｜疊合正規化曲線（對照用，不進交付）",
    "三條線疊在同一軸上。強調的是「發散」——但發散只是賽程長度的機械翻譯，"
    "而第 3 週之後三條完全重疊，畫布利用率很差。",
    figB.to_html(**opts), tableB,
    "此圖僅供比較設計方向，<b>不進最終交付</b>。同資料來源與限制見草稿 A。"
), encoding="utf-8")

(OUT / "draft-c-daily-vs-weekly.html").write_text(shell(
    "草稿 C｜同一場世足，日資料與週資料講出不同的故事（方法論，第二張）",
    "週平均把單日爆發抹平了：<b>日資料的最高點是決賽日 12/18，週資料的最高點卻在開幕週</b>。"
    "解析度的選擇會改變結論。",
    figC.to_html(**opts), tableC,
    "<b>重要</b>：兩條線來自<b>兩次獨立查詢</b>（日＝3 個月窗、週＝5 年窗），"
    "各自正規化，因此<b>只可比形狀與峰值位置，不可比高度</b>。<br>"
    "「被壓掉 6.8 倍」指的是同一週內日指數 61 對週指數 9 的落差，"
    "是兩種聚合方式的差異，不是兩個尺度的直接相除。<br>"
    "搜尋熱度 ≠ 訂閱數；賽事日期未查一手來源。"
), encoding="utf-8")

print("已產生：")
for p in sorted(OUT.iterdir()):
    print(f"  {p.name}  {p.stat().st_size:,} bytes")
