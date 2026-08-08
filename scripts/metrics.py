# -*- coding: utf-8 -*-
"""結論所依賴的四個量，集中在這裡並附測試（`tests/test_metrics.py`）。

抽出來的理由不是整潔，是這幾個函式有**會改變結論卻不會報錯**的路徑：
`half_life` 在「永遠回不到一半」時回 None、`spike_ratio` 在中位數為 0 時回 inf。
散在各腳本裡時，這些路徑沒有任何東西鎖住。

**期數而非天數**：所有「多久」一律回傳 index 步數，與資料頻率同單位
（日資料＝天、週資料＝週）。原本兩支腳本各自用 `.days` 與 `.days // 7`，
後者假設週與週之間永遠相差 7 天——缺一週就會算錯。
"""
from __future__ import annotations

import math


def spike_ratio(s):
    """尖峰比 = max ÷ 中位數。回傳 (ratio, max, idxmax)。

    中位數為 0 時回傳 `inf`——這是真實情況（小眾關鍵字過半期數為 0），
    不是錯誤，但呼叫端必須知道自己拿到的是 inf 而不是一個大數字。
    """
    med = s.median()
    mx = s.max()
    ratio = math.inf if med == 0 else round(mx / med, 2)
    return ratio, mx, s.idxmax()


def periods_to_threshold(s, peak_pos, threshold):
    """峰值之後，首次 <= threshold 所需的期數。回不到則 None。

    `peak_pos` 是 index 位置（非標籤）。只看峰值之後，不回頭看。
    """
    after = s.iloc[peak_pos + 1:]
    hit = after[after <= threshold]
    if len(hit) == 0:
        return None
    return s.index.get_loc(hit.index[0]) - peak_pos


def half_life(s, peak_pos=None):
    """峰值之後首次 <= 峰值/2 所需的期數。回傳 (期數, 峰值, 峰值標籤)。

    回不到一半時期數為 None——**這不是錯誤**，代表在觀測窗內沒有衰退到一半，
    呼叫端不得把它當成 0 或當成「很快」。
    """
    if peak_pos is None:
        peak_pos = int(s.values.argmax())
    peak = s.iloc[peak_pos]
    return periods_to_threshold(s, peak_pos, peak / 2), peak, s.index[peak_pos]


def baseline_band(s, peak_pos, lo_off=26, hi_off=5, qlo=0.25, qhi=0.75):
    """賽前基準帶：峰值前 `lo_off`~`hi_off` 期的 (p25, p75)。

    用分位數而非 min–max：基準窗可能含前一個事件（WBC 的窗含世足，max=36），
    min–max 會被單一污染期撐成無意義的寬帶。分位數對少數污染期穩健。
    `hi_off` 跳開緊鄰峰值的數期，避免賽前預熱污染基準。
    """
    if peak_pos - hi_off <= 0:
        raise ValueError(f"峰值位置 {peak_pos} 太靠前，取不到基準窗（需要 > {hi_off}）")
    win = s.iloc[max(0, peak_pos - lo_off): peak_pos - hi_off]
    if len(win) == 0:
        raise ValueError("基準窗為空")
    return float(win.quantile(qlo)), float(win.quantile(qhi))
