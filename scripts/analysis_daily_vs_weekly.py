"""兩項查核：
(A) 週級是否抹平了世足決賽日的單日爆發？（比對日資料與週資料）
(B) WBC 的賽前基準窗被世足尾巴污染 → 事後修正版基準（明確標示為事後，不取代預先登記的數字）
"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import warnings, datetime as dt
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd

from metrics import periods_to_threshold

RAW = REPO / "data" / "raw"
KW = 'Hami Video'

wk = pd.read_csv(RAW / "groupA_brand_5yr.csv", index_col=0, parse_dates=True)
wk = wk[~wk['isPartial'].astype(bool)][KW]
dy = pd.read_csv(RAW / "res_3mo_worldcup.csv", index_col=0, parse_dates=True)
dy = dy[~dy['isPartial'].astype(bool)][KW]

print("=" * 78)
print("(A) 週級是否抹平單日爆發？——世足決賽 2022-12-18")
print("=" * 78)
print("\n日資料（窗=2022-11-01~2023-01-31，3 詞，Netflix 佔 100）：")
for wstart in ['2022-11-20', '2022-12-11', '2022-12-18']:
    a = pd.Timestamp(wstart)
    b = a + pd.Timedelta(days=6)
    seg = dy[(dy.index >= a) & (dy.index <= b)]
    print(f"  {a.date()}~{b.date()}  日值={list(seg.values)}  平均={seg.mean():.1f} 最大={seg.max()}")

print("\n週資料（窗=2021-08~2026-08，5 詞）同期：")
for wstart in ['2022-11-20', '2022-12-11', '2022-12-18']:
    print(f"  {wstart} 週值 = {wk.loc[pd.Timestamp(wstart)]}")

peak_d = dy.idxmax()
print(f"\n  日資料全窗最高日 = {peak_d.date()} 值={dy.max()}（世足決賽日）")
print(f"  該日所屬週在週資料中的值 = {wk.loc[pd.Timestamp('2022-12-18')]}")
print(f"  週資料在整段世足期間的最高週 = {wk.loc['2022-11-20':'2022-12-25'].idxmax().date()}"
      f" 值={wk.loc['2022-11-20':'2022-12-25'].max()}")

print("\n" + "=" * 78)
print("(B) 事後修正基準（原定義的基準窗被前一事件污染）")
print("=" * 78)
EVENTS = {
    "2022 世界盃":  (dt.date(2022, 11, 20), dt.date(2022, 12, 18)),
    "2023 WBC":     (dt.date(2023, 3, 8),   dt.date(2023, 3, 21)),
    "2024 巴黎奧運": (dt.date(2024, 7, 26),  dt.date(2024, 8, 11)),
}
print("\n修正定義：基準窗改為峰值週前 26 ~ 前 6 週（20 週），取中位數；20 週窗不易被單一事件主導")
print("回歸週數 = 峰值後首次 <= 基準中位數 + 1（+1 為整數量化容差）\n")
rows = []
for name, (d0, d1) in EVENTS.items():
    lo, hi = pd.Timestamp(d0) - pd.Timedelta(weeks=2), pd.Timestamp(d1) + pd.Timedelta(weeks=2)
    win = wk[(wk.index >= lo) & (wk.index <= hi)]
    peak, pday = win.max(), win.idxmax()
    pi = wk.index.get_loc(pday)
    base_old = wk.iloc[max(0, pi - 13): pi - 5]
    base_new = wk.iloc[max(0, pi - 26): pi - 5]
    thr = base_new.median() + 1
    back = periods_to_threshold(wk, pi, thr)
    rows.append(dict(賽事=name, 峰值=peak,
                     原基準中位數=base_old.median(), 原基準上緣=base_old.max(),
                     新基準中位數=base_new.median(), 新門檻=thr,
                     新爆發倍率=round(peak / base_new.median(), 1), 新回歸週數=back))
    print(f"  {name}: 新基準窗 {base_new.index[0].date()}~{base_new.index[-1].date()} "
          f"值分佈 min={base_new.min()} p50={base_new.median():.1f} max={base_new.max()}")
print()
print(pd.DataFrame(rows).to_string(index=False))

print("\n■ 基準線漂移（品牌自然成長，非事件效應）")
for yr in [2022, 2023, 2024, 2025]:
    seg = wk[f'{yr}-01-01':f'{yr}-12-31']
    print(f"  {yr} 年 {KW} 中位數={seg.median():.1f}  p25={seg.quantile(.25):.1f} p75={seg.quantile(.75):.1f}")
