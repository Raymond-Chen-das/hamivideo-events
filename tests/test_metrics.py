# -*- coding: utf-8 -*-
"""metrics.py 的測試。重點在「會改變結論卻不會報錯」的路徑。

跑法：`pytest -q`（repo 根目錄）
"""
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from metrics import baseline_band, half_life, periods_to_threshold, spike_ratio  # noqa: E402


def wk(values, start="2022-01-02"):
    """建週序列，index 為每週一期。"""
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="7D"))


# ── spike_ratio ────────────────────────────────────────────────────────────
def test_spike_ratio_basic():
    ratio, mx, at = spike_ratio(wk([2, 2, 46, 2, 2]))
    assert ratio == 23.0 and mx == 46
    assert at == pd.Timestamp("2022-01-16")


def test_spike_ratio_median_zero_returns_inf():
    """過半期數為 0 時中位數為 0。必須回 inf，不得除以零炸掉、
    也不得悄悄回一個看起來正常的大數字。"""
    ratio, mx, _ = spike_ratio(wk([0, 0, 0, 5, 9]))
    assert math.isinf(ratio) and mx == 9


def test_spike_ratio_flat_series_is_one():
    """完全平坦（例如被泛用語意灌成底噪的 MOD）尖峰比趨近 1，
    這正是用來與品牌詞區分的判準。"""
    ratio, _, _ = spike_ratio(wk([13] * 10))
    assert ratio == 1.0


# ── half_life / periods_to_threshold ───────────────────────────────────────
def test_half_life_counts_periods_not_days():
    """回傳期數而非天數：週資料的 2 表示 2 週。
    原本用 `.days // 7`，缺一週就會算錯。"""
    periods, peak, at = half_life(wk([1, 36, 25, 17, 7]), peak_pos=1)
    assert periods == 2          # 36 → 17 <= 18 落在峰值後第 2 期
    assert peak == 36 and at == pd.Timestamp("2022-01-09")


def test_half_life_never_reached_returns_none():
    """觀測窗內沒有衰退到一半 → None。
    **不得當成 0，也不得當成「衰退很快」**——語意相反。"""
    periods, _, _ = half_life(wk([2, 100, 99, 98, 97]), peak_pos=1)
    assert periods is None


def test_half_life_ignores_pre_peak_dip():
    """只看峰值之後。峰值前的低點不算數，否則會回傳負期數或 0。"""
    periods, _, _ = half_life(wk([1, 1, 40, 30, 15]), peak_pos=2)
    assert periods == 2


def test_half_life_infers_peak_when_not_given():
    periods, peak, _ = half_life(wk([1, 36, 25, 17, 7]))
    assert periods == 2 and peak == 36


def test_periods_to_threshold_boundary_is_inclusive():
    """`<=` 而非 `<`：正好等於門檻就算回到基準。
    三場賽事的回歸週數全都落在等號上（世足 wk5=2 對帶上緣 2），
    改成嚴格小於會讓三個數字同時改變。"""
    s = wk([10, 5, 2, 2])
    assert periods_to_threshold(s, 0, 2) == 2


def test_periods_to_threshold_never_returns_none():
    assert periods_to_threshold(wk([10, 9, 8]), 0, 1) is None


# ── baseline_band ──────────────────────────────────────────────────────────
def test_baseline_band_is_robust_to_a_contaminating_event():
    """WBC 的基準窗含世足（max=36）。min–max 會被撐成 [1, 36]；
    p25–p75 必須把污染期擋在外面。

    污染比例照真實情況：21 期中 3 期（約 14%）。"""
    pre = [1, 2, 36, 17, 7, 2, 1, 2, 2, 2, 1, 2, 2, 1, 2, 2, 1, 2, 2, 1, 2]
    s = wk(pre + [1, 2, 32])
    lo, hi = baseline_band(s, peak_pos=23, lo_off=23, hi_off=2)
    assert (lo, hi) == (1.0, 2.0)
    assert hi < max(pre)               # 遠低於污染值 36


def test_baseline_band_breaks_down_under_heavy_contamination():
    """**p25–p75 不是無條件安全的。** 污染期佔到約四分之一時，
    p75 就會被抬高（此例 2.0 → 3.25）。

    這一則不是在測「正確行為」，是把**失效點寫死**：
    若日後新增的事件距前一事件太近、基準窗污染比例升高，
    這個定義就不再適用，必須改窗或改分位數，而不是照用。"""
    s = wk([1, 2, 36, 17, 7, 2, 1, 2, 2, 2, 1, 2, 2, 1, 2, 32])
    lo, hi = baseline_band(s, peak_pos=15, lo_off=15, hi_off=3)
    assert hi > 2.0, "污染比例偏高時 p75 應被抬升——若此處變綠，代表定義已改"


def test_baseline_band_skips_the_pre_event_ramp():
    """hi_off 跳開緊鄰峰值的數期。若不跳開，賽前預熱（13）會抬高基準。"""
    s = wk([2, 2, 2, 2, 2, 2, 3, 13, 46])
    lo, hi = baseline_band(s, peak_pos=8, lo_off=8, hi_off=3)
    assert hi == 2.0                   # 13 與 3 都被 hi_off 排除


def test_baseline_band_raises_when_window_unavailable():
    """峰值太靠前時取不到基準窗。必須明確拋錯，
    不得回傳一個用半個窗算出來、看起來正常的數字。"""
    with pytest.raises(ValueError):
        baseline_band(wk([1, 2, 40]), peak_pos=2, hi_off=5)


# ── 與實際資料的一致性（回歸鎖） ─────────────────────────────────────────────
def test_matches_published_results_on_real_data():
    """鎖住 README 與交付物裡的三個數字。資料或定義一改，這裡就會紅。"""
    raw = Path(__file__).resolve().parents[1] / "data" / "raw" / "groupA_brand_5yr.csv"
    df = pd.read_csv(raw, index_col=0, parse_dates=True)
    s = df[~df["isPartial"].astype(bool)]["Hami Video"]

    expected = {                       # 峰值日: (峰值, 基準帶, 回歸期數)
        "2022-11-20": (36, (1.0, 2.0), 5),
        "2023-03-05": (32, (1.0, 2.0), 3),
        "2024-07-28": (46, (2.0, 3.0), 3),
    }
    for day, (peak, band, back) in expected.items():
        pos = s.index.get_loc(pd.Timestamp(day))
        assert s.iloc[pos] == peak
        assert baseline_band(s, pos) == band
        assert periods_to_threshold(s, pos, band[1]) == back
