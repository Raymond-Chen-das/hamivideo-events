# -*- coding: utf-8 -*-
"""(1) 定位 shapes 消失的根因  (2) 計算基準帶的候選定義"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import warnings
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

print("=" * 74)
print("(1) 假說：add_vrect/add_hline 的 exclude_empty_subplots 預設為 True，")
print("    而我在『尚未加 trace』的空 subplot 上先加 shape → 被靜默丟棄")
print("=" * 74)

f1 = make_subplots(rows=1, cols=2)
f1.add_vrect(x0=1, x1=2, row=1, col=1, fillcolor="red", line_width=0)
f1.add_hline(y=5, row=1, col=1)
f1.add_trace(go.Scatter(x=[0, 3], y=[1, 9]), row=1, col=1)
print(f"  先 shape 後 trace           → shapes = {len(f1.layout.shapes)}")

f2 = make_subplots(rows=1, cols=2)
f2.add_trace(go.Scatter(x=[0, 3], y=[1, 9]), row=1, col=1)
f2.add_vrect(x0=1, x1=2, row=1, col=1, fillcolor="red", line_width=0)
f2.add_hline(y=5, row=1, col=1)
print(f"  先 trace 後 shape           → shapes = {len(f2.layout.shapes)}")

f3 = make_subplots(rows=1, cols=2)
f3.add_vrect(x0=1, x1=2, row=1, col=1, fillcolor="red", line_width=0,
             exclude_empty_subplots=False)
f3.add_trace(go.Scatter(x=[0, 3], y=[1, 9]), row=1, col=1)
print(f"  先 shape + exclude=False    → shapes = {len(f3.layout.shapes)}")

f4 = make_subplots(rows=1, cols=2)
f4.add_trace(go.Scatter(x=[0, 3], y=[1, 9]), row=1, col=1)
f4.add_vrect(x0=1, x1=2, row=1, col=1, fillcolor="red", line_width=0)
f4.update_layout(height=400, paper_bgcolor="#fff")
print(f"  trace→shape→update_layout   → shapes = {len(f4.layout.shapes)}  (檢查是否被覆蓋)")

print("\n" + "=" * 74)
print("(2) 基準帶：找一個不被前一事件污染的定義")
print("=" * 74)
RAW = REPO / "data" / "raw"
wk = pd.read_csv(RAW / "groupA_brand_5yr.csv", index_col=0, parse_dates=True)
wk = wk[~wk["isPartial"].astype(bool)]["Hami Video"]
EV = {"2022 世界盃": "2022-11-20", "2023 WBC": "2023-03-05", "2024 巴黎奧運": "2024-07-28"}
for name, pk in EV.items():
    pi = wk.index.get_loc(pd.Timestamp(pk))
    pre3 = [int(wk.iloc[pi + k]) for k in (-3, -2, -1)]
    w20 = wk.iloc[max(0, pi - 26): pi - 5]
    print(f"\n■ {name}  峰值={int(wk.iloc[pi])}")
    print(f"   顯示區間內的賽前三週 (x=-3,-2,-1) = {pre3}")
    print(f"   基準窗(前26~前6週) n={len(w20)} min={w20.min()} p25={w20.quantile(.25):.1f} "
          f"p50={w20.median():.1f} p75={w20.quantile(.75):.1f} p90={w20.quantile(.90):.1f} max={w20.max()}")
    print(f"   → p25–p75 帶 = [{w20.quantile(.25):.1f}, {w20.quantile(.75):.1f}]   "
          f"賽前三週是否全落帶內: {all(w20.quantile(.25) <= v <= w20.quantile(.75) for v in pre3)}")
    print(f"   → p25–p90 帶 = [{w20.quantile(.25):.1f}, {w20.quantile(.90):.1f}]   "
          f"賽前三週是否全落帶內: {all(w20.quantile(.25) <= v <= w20.quantile(.90) for v in pre3)}")
