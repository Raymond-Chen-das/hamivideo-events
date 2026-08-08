"""視覺化決策的前置查核：以「峰值週」對齊 vs 以「賽事結束週」對齊，哪一種讓發現更清楚？"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import warnings, datetime as dt
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd

RAW = REPO / "data" / "raw"
s = pd.read_csv(RAW / "groupA_brand_5yr.csv", index_col=0, parse_dates=True)
s = s[~s['isPartial'].astype(bool)]['Hami Video']

# 賽事期間（參考日，未查一手來源）。WBC 另記台灣賽事期間。
EV = {
    "世界盃":   dict(start=dt.date(2022, 11, 20), end=dt.date(2022, 12, 18), peak='2022-11-20'),
    "WBC":     dict(start=dt.date(2023, 3, 8),   end=dt.date(2023, 3, 12),  peak='2023-03-05'),  # 台灣賽事
    "巴黎奧運": dict(start=dt.date(2024, 7, 26),  end=dt.date(2024, 8, 11),  peak='2024-07-28'),
}

print("=" * 84)
print("賽程長度 vs 峰值後軌跡（檢查『賽事期間維持、結束即斷崖』是否成立）")
print("=" * 84)
for name, e in EV.items():
    pk = pd.Timestamp(e['peak'])
    pi = s.index.get_loc(pk)
    peak = s.iloc[pi]
    endw = s.index[s.index <= pd.Timestamp(e['end'])][-1]   # 賽事結束日所屬週
    ei = s.index.get_loc(endw)
    dur_w = (e['end'] - e['start']).days / 7
    print(f"\n■ {name}  賽程 {e['start']} ~ {e['end']}（{dur_w:.1f} 週）  峰值週={pk.date()} 峰值={peak}")
    print(f"  結束日所屬週={endw.date()}  = 峰值後第 {ei-pi} 週")
    for k in range(0, 7):
        if pi + k >= len(s):
            break
        d, v = s.index[pi + k], s.iloc[pi + k]
        tag = "賽事進行中" if d.date() <= e['end'] else "賽事已結束"
        print(f"    峰值後第 {k} 週 {d.date()}  值={v:>3}  正規化={v/peak:.3f}   {tag}")

print("\n" + "=" * 84)
print("以「賽事結束週」對齊（t=0 為結束日所屬週）——三條會不會疊合？")
print("=" * 84)
hdr = "  賽事        " + "".join(f"{t:>8}" for t in range(-2, 5))
print(hdr)
for name, e in EV.items():
    pk = pd.Timestamp(e['peak'])
    peak = s.loc[pk]
    endw = s.index[s.index <= pd.Timestamp(e['end'])][-1]
    ei = s.index.get_loc(endw)
    row = ""
    for t in range(-2, 5):
        j = ei + t
        row += f"{s.iloc[j]/peak:>8.3f}" if 0 <= j < len(s) else f"{'--':>8}"
    print(f"  {name:<12}" + row)

print("\n以「峰值週」對齊（對照組）")
print(hdr.replace("賽事        ", "賽事        "))
for name, e in EV.items():
    pk = pd.Timestamp(e['peak'])
    pi = s.index.get_loc(pk)
    peak = s.iloc[pi]
    row = ""
    for t in range(-2, 5):
        j = pi + t
        row += f"{s.iloc[j]/peak:>8.3f}" if 0 <= j < len(s) else f"{'--':>8}"
    print(f"  {name:<12}" + row)
