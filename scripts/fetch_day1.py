"""Day 1 — 可重現性採集。這是 README 指名的重新取數入口。

**取數策略：fail-fast。第一個 429 就中止當天全部請求，不重試、不等待。**

依據是實測而非偏好：配額為**觸發式封鎖**，不是每分鐘節流——踩線後 0/30 橫跨
47.5 小時，300 秒退避與 25 分鐘閒置冷卻皆無效（紀錄見 ``logs/quota_attempts.csv``）。
更關鍵的是**不知道 429 本身是否也消耗配額**：若消耗，重試等於加深封鎖。
fail-fast 在「消耗」與「不消耗」兩種假設下都是對的。

每一次嘗試（成功或失敗）都寫入 ``logs/quota_attempts.csv``（append-only）。

> 本檔早期版本採 300 秒退避重試，那是執行當下的假設，已被上述實測推翻。
> 舊行為保留在 git 歷史與 quota_attempts.csv 的實際嘗試紀錄裡。
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
DAY = "Day1"


class QuotaBlocked(Exception):
    """收到 429。fail-fast：當天不再發任何請求。"""


COLS = ["timestamp_iso", "day_label", "query_label", "kw_list", "timeframe", "geo", "hl", "tz",
        "attempt_no", "result", "error_type", "elapsed_sec", "notes"]

def log(row):
    new = not LOGFILE.exists()
    with LOGFILE.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow(row)

def fetch(query_label, kw_list, timeframe, out_name):
    """發一次請求。429 一律拋 QuotaBlocked，由呼叫端中止當天所有後續請求。"""
    print(f"\n{'='*72}\n[{query_label}] kw={kw_list} tf='{timeframe}'", flush=True)
    t0 = time.time()
    ts = dt.datetime.now().isoformat(timespec='seconds')
    base = dict(timestamp_iso=ts, day_label=DAY, query_label=query_label,
                kw_list="|".join(kw_list), timeframe=timeframe, geo=GEO, hl=HL, tz=TZ,
                attempt_no=1)
    try:
        pt = TrendReq(hl=HL, tz=TZ)
        pt.build_payload(kw_list=kw_list, geo=GEO, timeframe=timeframe)
        df = pt.interest_over_time()
        el = round(time.time() - t0, 2)
        log(dict(**base, result="ok", error_type="", elapsed_sec=el,
                 notes=f"shape={df.shape}"))
        df.to_csv(RAW / out_name, encoding='utf-8-sig')
        print(f"  OK ({ts}, {el}s) shape={df.shape} -> raw/{out_name}", flush=True)
        return df
    except TooManyRequestsError:
        el = round(time.time() - t0, 2)
        log(dict(**base, result="429",
                 error_type="pytrends.exceptions.TooManyRequestsError",
                 elapsed_sec=el, notes="fail-fast_abort"))
        print(f"  429 ({ts}, {el}s) -> fail-fast：中止當天所有請求，不重試", flush=True)
        raise QuotaBlocked(query_label)
    except Exception as e:
        el = round(time.time() - t0, 2)
        log(dict(**base, result="other",
                 error_type=f"{type(e).__module__}.{type(e).__name__}", elapsed_sec=el,
                 notes=str(e)[:200]))
        print(f"  非429錯誤: {type(e).__name__}: {e}", flush=True)
        return None

def clean(df):
    return df[~df['isPartial'].astype(bool)] if 'isPartial' in df.columns else df

# half_life 已移入 metrics.py 並附測試（tests/test_metrics.py）。
# 回傳單位由「天數」改為「期數」——日資料兩者相同，此處行為不變。

KW = ['Hami Video', 'Netflix', 'Disney+']
print("Day 1 START", dt.datetime.now().isoformat(timespec='seconds'), flush=True)

# fail-fast：第一個 429 就中止，不重試也不等待。
# 兩個查詢之間原本有 60 秒間隔，一併移除——它建立在「節流」的假設上，
# 而實測顯示配額是觸發式封鎖，等待不會恢復額度。
a2 = b2 = None
try:
    a2 = fetch("A_worldcup_daily", KW, '2022-11-01 2023-01-31', "run2_worldcup_daily.csv")
    b2 = fetch("B_monthly_7.5yr", KW, '2019-01-01 2026-08-02', "run2_21query.csv")
except QuotaBlocked as blocked:
    print(f"\n{'!'*72}\n配額封鎖於 [{blocked}]，當天中止。", flush=True)
    print("未取得的項目一律記為【未驗證】，不以其他查詢湊數。", flush=True)
    print(f"嘗試紀錄：{LOGFILE}\n{'!'*72}", flush=True)

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
