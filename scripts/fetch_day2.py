"""Day 2 — 中華電信 MOD 對照 ＋ B 組事件詞。依 prompt 第三、四、五節。
硬上限 4 次嘗試（每查詢最多 2），重試間隔 >=300s，每次嘗試都記 log。
注意：本次執行未滿「Day1/Day2 間隔 >=24h」的規格要求，log 的 notes 欄已標記。
"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import csv, time, warnings, datetime as dt
from pathlib import Path
warnings.filterwarnings("ignore")
import pandas as pd
from pytrends.request import TrendReq
from pytrends.exceptions import TooManyRequestsError

from metrics import spike_ratio

BASE = REPO
RAW, LOGS = BASE / "data" / "raw", BASE / "logs"
LOGFILE = LOGS / "quota_attempts.csv"
HL, TZ, GEO = 'zh-TW', -480, 'TW'
TF5, RETRY_GAP, DAY = '2021-08-03 2026-08-02', 300, "Day2"
VIOLATION = "interval<24h_from_Day1"
COLS = ["timestamp_iso", "day_label", "query_label", "kw_list", "timeframe", "geo", "hl", "tz",
        "attempt_no", "result", "error_type", "elapsed_sec", "notes"]

def log(**kw):
    new = not LOGFILE.exists()
    with LOGFILE.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow(kw)

def fetch(query_label, kw_list, out_name, max_attempts=2):
    print(f"\n{'='*72}\n[{query_label}] kw={kw_list} tf='{TF5}'", flush=True)
    for n in range(1, max_attempts + 1):
        t0, ts = time.time(), dt.datetime.now().isoformat(timespec='seconds')
        base = dict(timestamp_iso=ts, day_label=DAY, query_label=query_label,
                    kw_list="|".join(kw_list), timeframe=TF5, geo=GEO, hl=HL, tz=TZ, attempt_no=n)
        try:
            pt = TrendReq(hl=HL, tz=TZ)
            pt.build_payload(kw_list=kw_list, geo=GEO, timeframe=TF5)
            df = pt.interest_over_time()
            el = round(time.time() - t0, 2)
            log(**base, result="ok", error_type="", elapsed_sec=el,
                notes=f"shape={df.shape};{VIOLATION}")
            df.to_csv(RAW / out_name, encoding='utf-8-sig')
            print(f"  OK 第 {n} 次 ({ts}, {el}s) shape={df.shape} -> raw/{out_name}", flush=True)
            return df
        except TooManyRequestsError:
            el = round(time.time() - t0, 2)
            log(**base, result="429", error_type="pytrends.exceptions.TooManyRequestsError",
                elapsed_sec=el, notes=VIOLATION)
            print(f"  429 第 {n} 次 ({ts}, {el}s)", flush=True)
            if n < max_attempts:
                print(f"  -> 等 {RETRY_GAP}s 後重試同一查詢", flush=True)
                time.sleep(RETRY_GAP)
        except Exception as e:
            el = round(time.time() - t0, 2)
            log(**base, result="other", error_type=f"{type(e).__module__}.{type(e).__name__}",
                elapsed_sec=el, notes=f"{VIOLATION};{str(e)[:150]}")
            print(f"  非429錯誤 第 {n} 次: {type(e).__name__}: {e}", flush=True)
            return None
    print(f"  放棄（用完 {max_attempts} 次嘗試）", flush=True)
    return None

def clean(df):
    return df[~df['isPartial'].astype(bool)] if 'isPartial' in df.columns else df

# spike_ratio 已移入 metrics.py 並附測試（tests/test_metrics.py），行為不變。

print("Day 2 START", dt.datetime.now().isoformat(timespec='seconds'), flush=True)

mod = fetch("MOD_control", ['MOD', '中華電信 MOD', 'Hami Video'], "mod_control.csv")
time.sleep(60)
evt = fetch("groupB_event", ['世界盃', 'WBC', '經典賽'], "groupB_event_5yr.csv")

# ---- 判準 4.2 ----
print(f"\n{'#'*72}\n### 判準 4.2  中華電信 MOD 對照", flush=True)
if mod is None:
    print("  未取得 -> 未驗證", flush=True)
else:
    c = clean(mod)
    for k in ['MOD', '中華電信 MOD', 'Hami Video']:
        sr, mx, mxd = spike_ratio(c[k])
        print(f"  {k!r:16s} 尖峰比={sr:>7} (max={mx}, 中位數={c[k].median()}) "
              f"零值比例={100*(c[k]==0).mean():5.1f}% 峰值週={mxd.date()}", flush=True)
        print(f"      前5高峰: " + ", ".join(f"{i.date()}={v}" for i, v in c[k].nlargest(5).items()), flush=True)
    print(f"  相關係數 MOD vs 中華電信 MOD = {c['MOD'].corr(c['中華電信 MOD']):.4f}", flush=True)

# ---- 判準 4.3 ----
print(f"\n{'#'*72}\n### 判準 4.3  B 組事件詞", flush=True)
BASELINE = {'世界盃': dt.date(2022, 11, 20), 'WBC': dt.date(2023, 3, 8), '經典賽': dt.date(2023, 3, 8)}
if evt is None:
    print("  未取得 -> 未驗證", flush=True)
else:
    c = clean(evt)
    for k in ['世界盃', 'WBC', '經典賽']:
        sr, mx, mxd = spike_ratio(c[k])
        gap = (mxd.date() - BASELINE[k]).days
        print(f"  {k!r:8s} 尖峰比={sr:>7} (max={mx}, 中位數={c[k].median()}) "
              f"零值比例={100*(c[k]==0).mean():5.1f}%", flush=True)
        print(f"      峰值週={mxd.date()}  賽事基準={BASELINE[k]}  落差={gap} 天 ({gap/7:.1f} 週)", flush=True)
        print(f"      前5高峰: " + ", ".join(f"{i.date()}={v}" for i, v in c[k].nlargest(5).items()), flush=True)
    print(f"  WBC vs 經典賽 相關係數 = {c['WBC'].corr(c['經典賽']):.4f}（重疊程度）", flush=True)

print("\nDay 2 END", dt.datetime.now().isoformat(timespec='seconds'), flush=True)
