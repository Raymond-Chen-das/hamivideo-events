"""週級主線分析 — 三場賽事的熱度衰退比較。零 API 請求，只讀 raw/groupA_brand_5yr.csv。

【看資料前寫死的定義】
- 賽事參考日：本 session 未查一手來源，屬待驗事實，僅作對齊用
    2022 FIFA 世界盃  2022-11-20 開幕 ~ 2022-12-18 決賽
    2023 WBC          2023-03-08 ~ 2023-03-21（台灣賽事 3/8–3/12）
    2024 巴黎奧運      2024-07-26 開幕 ~ 2024-08-11 閉幕
- 峰值週      = 賽事期間前後各 2 週內，Hami Video 的最大值所在週
- 賽前基準窗  = 峰值週的前 13 ~ 前 6 週（共 8 週），刻意跳開賽前 5 週以避開預熱污染
- 基準中位數 / 基準上緣 = 該窗的 median / max
- 爆發倍率    = 峰值 ÷ 基準中位數
- 半衰期(週)  = 峰值週之後，首次 <= 峰值/2 所需的週數
- 回歸週數    = 峰值週之後，首次 <= 基準上緣 所需的週數
"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import warnings, datetime as dt
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd

from metrics import periods_to_threshold

from _data import require

RAW = REPO / "data" / "raw"
KW = 'Hami Video'

EVENTS = {
    "2022 世界盃":  (dt.date(2022, 11, 20), dt.date(2022, 12, 18)),
    "2023 WBC":     (dt.date(2023, 3, 8),   dt.date(2023, 3, 21)),
    "2024 巴黎奧運": (dt.date(2024, 7, 26),  dt.date(2024, 8, 11)),
}

df = pd.read_csv(require("groupA_brand_5yr.csv"), index_col=0, parse_dates=True)
df = df[~df['isPartial'].astype(bool)]
s = df[KW]
print(f"資料：{RAW.name}/groupA_brand_5yr.csv  週解析度  {s.index[0].date()} ~ {s.index[-1].date()}  n={len(s)}")
print(f"全期 {KW}：中位數={s.median():.0f} p75={s.quantile(.75):.0f} max={s.max()} 零值={100*(s==0).mean():.1f}%")
print(f"全期基準（非賽事期間的常態水準）中位數 = {s.median():.0f}\n")

rows = []
for name, (d0, d1) in EVENTS.items():
    lo = pd.Timestamp(d0) - pd.Timedelta(weeks=2)
    hi = pd.Timestamp(d1) + pd.Timedelta(weeks=2)
    win = s[(s.index >= lo) & (s.index <= hi)]
    peak = win.max()
    pday = win.idxmax()
    pi = s.index.get_loc(pday)

    base = s.iloc[max(0, pi - 13): pi - 5]
    bmed, bmax = base.median(), base.max()

    half = periods_to_threshold(s, pi, peak / 2)
    back = periods_to_threshold(s, pi, bmax)

    print("=" * 78)
    print(f"■ {name}   賽事期間 {d0} ~ {d1}（參考日，未查一手來源）")
    print(f"  峰值週={pday.date()}  峰值={peak}   （峰值週落在賽事{'期間內' if d0 <= pday.date() <= d1 else '期間外'}）")
    print(f"  賽前基準窗 {base.index[0].date()} ~ {base.index[-1].date()}：中位數={bmed:.1f} 上緣={bmax} 值={list(base.values)}")
    print(f"  爆發倍率 = {peak}/{bmed:.1f} = {peak/bmed:.1f}x")
    print(f"  半衰期 = {half} 週   （首次 <= {peak/2:.1f}）")
    print(f"  回歸基準 = {back} 週  （首次 <= 上緣 {bmax}）")
    traj = s.iloc[pi: pi + 17]
    print(f"  峰後軌跡（第 0~16 週）: {list(traj.values)}")
    norm = [round(v / peak, 3) for v in traj.values]
    print(f"  正規化軌跡（÷峰值）    : {norm}")
    rows.append(dict(賽事=name, 峰值週=pday.date(), 峰值=peak, 基準中位數=bmed, 基準上緣=bmax,
                     爆發倍率=round(peak / bmed, 1), 半衰期週=half, 回歸基準週=back))

print("\n" + "=" * 78)
print("■ 三場賽事對照（同一次查詢、同一尺度，直接可比）\n")
print(pd.DataFrame(rows).to_string(index=False))

print("\n■ 正規化衰退曲線對照（峰值=1.000）")
hdr = "  週      " + "".join(f"{i:>7}" for i in range(0, 13))
print(hdr)
for name, (d0, d1) in EVENTS.items():
    lo = pd.Timestamp(d0) - pd.Timedelta(weeks=2)
    hi = pd.Timestamp(d1) + pd.Timedelta(weeks=2)
    win = s[(s.index >= lo) & (s.index <= hi)]
    pi = s.index.get_loc(win.idxmax())
    peak = win.max()
    traj = s.iloc[pi: pi + 13]
    print(f"  {name:<12}" + "".join(f"{v/peak:>7.3f}" for v in traj.values))
