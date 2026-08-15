"""Day 2 — 中華電信 MOD 對照 ＋ B 組事件詞。

**取數策略：fail-fast。第一個 429 就中止當天全部請求，不重試、不等待。**

依據是實測而非偏好：配額為**觸發式封鎖**，不是每分鐘節流——踩線後 0/30 橫跨
47.5 小時，300 秒退避與 25 分鐘閒置冷卻皆無效（紀錄見 ``logs/quota_attempts.csv``）。
更關鍵的是**不知道 429 本身是否也消耗配額**：若消耗，重試等於加深封鎖。
fail-fast 在「消耗」與「不消耗」兩種假設下都是對的，這才是它成立的理由，
而不只是「重試沒用」。

每一次嘗試（成功或失敗）都寫入 ``logs/quota_attempts.csv``（append-only）。

> 本檔早期版本採 300 秒退避重試，那是執行當下的假設，已被上述實測推翻。
> 舊行為保留在 git 歷史與 quota_attempts.csv 的實際嘗試紀錄裡，不在此重演。
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
TF5, DAY = '2021-08-03 2026-08-02', "Day2"
VIOLATION = "interval<24h_from_Day1"


class QuotaBlocked(Exception):
    """收到 429。fail-fast：當天不再發任何請求。"""
COLS = ["timestamp_iso", "day_label", "query_label", "kw_list", "timeframe", "geo", "hl", "tz",
        "attempt_no", "result", "error_type", "elapsed_sec", "notes"]

def log(**kw):
    new = not LOGFILE.exists()
    with LOGFILE.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow(kw)

def fetch(query_label, kw_list, out_name):
    """發一次請求。429 一律拋 QuotaBlocked，由呼叫端中止當天所有後續請求。"""
    print(f"\n{'='*72}\n[{query_label}] kw={kw_list} tf='{TF5}'", flush=True)
    t0, ts = time.time(), dt.datetime.now().isoformat(timespec='seconds')
    base = dict(timestamp_iso=ts, day_label=DAY, query_label=query_label,
                kw_list="|".join(kw_list), timeframe=TF5, geo=GEO, hl=HL, tz=TZ, attempt_no=1)
    try:
        pt = TrendReq(hl=HL, tz=TZ)
        pt.build_payload(kw_list=kw_list, geo=GEO, timeframe=TF5)
        df = pt.interest_over_time()
        el = round(time.time() - t0, 2)
        log(**base, result="ok", error_type="", elapsed_sec=el,
            notes=f"shape={df.shape};{VIOLATION}")
        df.to_csv(RAW / out_name, encoding='utf-8-sig')
        print(f"  OK ({ts}, {el}s) shape={df.shape} -> raw/{out_name}", flush=True)
        return df
    except TooManyRequestsError:
        el = round(time.time() - t0, 2)
        log(**base, result="429", error_type="pytrends.exceptions.TooManyRequestsError",
            elapsed_sec=el, notes=f"{VIOLATION};fail-fast_abort")
        print(f"  429 ({ts}, {el}s) -> fail-fast：中止當天所有請求，不重試", flush=True)
        raise QuotaBlocked(query_label)
    except Exception as e:
        el = round(time.time() - t0, 2)
        log(**base, result="other", error_type=f"{type(e).__module__}.{type(e).__name__}",
            elapsed_sec=el, notes=f"{VIOLATION};{str(e)[:150]}")
        print(f"  非429錯誤: {type(e).__name__}: {e}", flush=True)
        return None

def clean(df):
    return df[~df['isPartial'].astype(bool)] if 'isPartial' in df.columns else df

# spike_ratio 已移入 metrics.py 並附測試（tests/test_metrics.py），行為不變。

print("Day 2 START", dt.datetime.now().isoformat(timespec='seconds'), flush=True)

# fail-fast：第一個 429 就中止，不重試也不等待。
# 兩個查詢之間原本有 60 秒間隔，一併移除——它建立在「節流」的假設上，
# 而實測顯示配額是觸發式封鎖，等待不會恢復額度。
mod = evt = None
try:
    mod = fetch("MOD_control", ['MOD', '中華電信 MOD', 'Hami Video'], "mod_control.csv")
    evt = fetch("groupB_event", ['世界盃', 'WBC', '經典賽'], "groupB_event_5yr.csv")
except QuotaBlocked as blocked:
    print(f"\n{'!'*72}\n配額封鎖於 [{blocked}]，當天中止。", flush=True)
    print("未取得的項目一律記為【未驗證】，不以其他查詢湊數。", flush=True)
    print(f"嘗試紀錄：{LOGFILE}\n{'!'*72}", flush=True)

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
