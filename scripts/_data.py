# -*- coding: utf-8 -*-
"""原始快照的存取守衛。

`data/raw/*.csv` **不隨版控散布**——它們是 `pytrends` 從 Google Trends 的非官方
端點取得的，該服務條款對再散布的規範未經確認，所以不放進公開 repo。
（圖表與摘要是靜態產出，不受影響，照常隨 repo 提供。）

因此在乾淨 clone 上跑分析腳本會缺檔。本模組的職責是讓那件事
**明確地失敗並說明怎麼補**，而不是丟一個看不出所以然的 FileNotFoundError——
「明確報錯而非靜默失敗」是這個 repo 一路在守的同一條規則。
"""

from __future__ import annotations

from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

_HOWTO = """
原始快照不隨版控散布（Google Trends 服務條款對再散布的規範未經確認）。

重新取得：
    python scripts/fetch_day1.py       # 會消耗配額，先讀 docs/prompt-verify-google-trends.md

⚠️ 配額是**觸發式封鎖**而非每分鐘節流——實測踩線後 0/30 橫跨 47.5 小時，
   退避與冷卻皆無效。不要迴圈重試。

不需要原始資料就能看的東西：
    charts/decay-by-event.html     主圖（靜態，已隨 repo 提供）
    charts/daily-vs-weekly.html    方法圖
    charts/onepager.html / .pdf    摘要
    README.md                      全部結果數字
"""


def require(filename: str) -> Path:
    """回傳快照路徑；缺檔則拋出帶重生指示的錯誤。"""
    p = RAW / filename
    if not p.exists():
        raise FileNotFoundError(
            f"找不到原始快照：data/raw/{filename}\n{_HOWTO}"
        )
    return p


def available(filename: str) -> bool:
    """給測試用：資料在不在，決定要不要 skip。"""
    return (RAW / filename).exists()
