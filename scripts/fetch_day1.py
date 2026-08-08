"""Day 1 — 可重現性。依 prompt 第三、四、五節執行。
硬上限 4 次嘗試（查詢 A 最多 2、查詢 B 最多 2），重試間隔 >= 300s，每次嘗試都記 log。
"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import csv, time, sys, warnings, datetime as dt
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

from metrics import half_life

BASE = REPO
RAW, LOGS = BASE / "data" / "raw", BASE / "logs"
LOGFILE = LOGS / "quota_attempts.csv"
HL, TZ, GEO = 'zh-TW', -480, 'TW'
RETRY_GAP = 300
DAY = "Day1"
COLS = ["timestamp_iso", "day_label", "query_label", "kw_list", "timeframe", "geo", "hl", "tz",
        "attempt_no", "result", "error_type", "elapsed_sec", "notes"]

def log(row):
    new = not LOGFILE.exists()
    with LOGFILE.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow(row)

def fetch(query_label, kw_list, timeframe, out_name, max_attempts):
    print(f"\n{'='*72}\n[{query_label}] kw={kw_list} tf='{timeframe}'", flush=True)
    for n in range(1, max_attempts + 1):
        t0 = time.time()
        ts = dt.datetime.now().isoformat(timespec='seconds')
        try:
            pt = TrendReq(hl=HL, tz=TZ)
            pt.build_payload(kw_list=kw_list, geo=GEO, timeframe=timeframe)
            df = pt.interest_over_time()
            el = round(time.time() - t0, 2)
            log(dict(timestamp_iso=ts, day_label=DAY, query_label=query_label,
                     kw_list="|".join(kw_list), timeframe=timeframe, geo=GEO, hl=HL, tz=TZ,
                     attempt_no=n, result="ok", error_type="", elapsed_sec=el,
                     notes=f"shape={df.shape}"))
            df.to_csv(RAW / out_name, encoding='utf-8-sig')
            print(f"  OK 第 {n} 次 ({ts}, {el}s) shape={df.shape} -> raw/{out_name}", flush=True)
            return df
        except TooManyRequestsError:
            el = round(time.time() - t0, 2)
            log(dict(timestamp_iso=ts, day_label=DAY, query_label=query_label,
                     kw_list="|".join(kw_list), timeframe=timeframe, geo=GEO, hl=HL, tz=TZ,
                     attempt_no=n, result="429", error_type="pytrends.exceptions.TooManyRequestsError",
                     elapsed_sec=el, notes=""))
            print(f"  429 第 {n} 次 ({ts}, {el}s)", flush=True)
            if n < max_attempts:
                print(f"  -> 等 {RETRY_GAP}s 後重試同一查詢", flush=True)
                time.sleep(RETRY_GAP)
        except Exception as e:
            el = round(time.time() - t0, 2)
            log(dict(timestamp_iso=ts, day_label=DAY, query_label=query_label,
                     kw_list="|".join(kw_list), timeframe=timeframe, geo=GEO, hl=HL, tz=TZ,
                     attempt_no=n, result="other",
                     error_type=f"{type(e).__module__}.{type(e).__name__}", elapsed_sec=el,
                     notes=str(e)[:200]))
            print(f"  非429錯誤 第 {n} 次: {type(e).__name__}: {e}", flush=True)
            return None
    print(f"  放棄（用完 {max_attempts} 次嘗試）", flush=True)
    return None

def clean(df):
    return df[~df['isPartial'].astype(bool)] if 'isPartial' in df.columns else df

# half_life 已移入 metrics.py 並附測試（tests/test_metrics.py）。
# 回傳單位由「天數」改為「期數」——日資料兩者相同，此處行為不變。

KW = ['Hami Video', 'Netflix', 'Disney+']
print("Day 1 START", dt.datetime.now().isoformat(timespec='seconds'), flush=True)

a2 = fetch("A_worldcup_daily", KW, '2022-11-01 2023-01-31', "run2_worldcup_daily.csv", 2)
time.sleep(60)
b2 = fetch("B_monthly_7.5yr", KW, '2019-01-01 2026-08-02', "run2_21query.csv", 2)

def compare(tag, p1, df2, primary):
    print(f"\n{'#'*72}\n### 比對 {tag}", flush=True)
    if df2 is None:
        print("  run2 未取得 -> 未驗證", flush=True); return
    r1 = clean(pd.read_csv(p1, index_col=0, parse_dates=True))
    r2 = clean(df2)
    common = r1.index.intersection(r2.index)
    print(f"  run1 n={len(r1)} run2 n={len(r2)} 共同期數={len(common)}", flush=True)
    a, b = r1.loc[common], r2.loc[common]
    for c in KW:
        d = (a[c] - b[c]).abs()
        nz = d[d > 0]
        print(f"  {c!r:14s} 有差異期數={len(nz)}/{len(d)} ({100*len(nz)/len(d):.1f}%) "
              f"逐點差異中位數={d.median():.2f} 最大={d.max()} 相關係數={a[c].corr(b[c]):.6f}", flush=True)
    if primary:
        h1, p1v, d1 = half_life(a['Hami Video'])
        h2, p2v, d2 = half_life(b['Hami Video'])
        print(f"\n  --- 判準 4.1 主要測項（Hami Video）---", flush=True)
        print(f"  run1 峰值={p1v} 峰值日={d1.date()} 半衰期={h1} 天", flush=True)
        print(f"  run2 峰值={p2v} 峰值日={d2.date()} 半衰期={h2} 天", flush=True)
        print(f"  峰值差={abs(p1v-p2v)}  峰值日相同={d1==d2}  "
              f"半衰期差={abs(h1-h2) if (h1 is not None and h2 is not None) else 'N/A'}", flush=True)

compare("查詢 A（世足日窗，主要）", RAW / "res_3mo_worldcup.csv", a2, True)
compare("查詢 B（7.5 年月查詢，次要）", RAW / "run1_21query.csv", b2, False)

print("\nDay 1 END", dt.datetime.now().isoformat(timespec='seconds'), flush=True)
