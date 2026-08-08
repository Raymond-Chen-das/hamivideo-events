# hamivideo-events

**How fast does the search interest from a major sporting event decay?**
An event study on Hami Video (Chunghwa Telecom's streaming service) across three
international tournaments, using Google Trends as the only observable signal.

## What

Three tournaments, one brand, one question: after the games end, does elevated
attention persist, or does it collapse back to where it started?

**Finding:** search interest returns to the pre-event baseline within 1–2 weeks
after each tournament ends — in all three cases. **At this data's resolution, no
residual lift is observable.** In other words, a tournament produces a *pulse*,
not a *step*.

The differences in decay *shape* between the three events are almost entirely a
mechanical consequence of how long each tournament ran. The non-trivial result is
the convergence, not the divergence.

## Method

**Signal.** Google Trends, geo `TW`, keyword `Hami Video`, weekly resolution,
2021-08-01 → 2026-07-26 (n = 261 weeks, 0.0% zero values). All five brand keywords
were queried together so the three events share one normalization scale and are
therefore directly comparable — this is the reason weekly is the primary unit, not
daily.

**Metrics, registered before looking at the data.**

| Quantity | Definition |
|---|---|
| Peak week | Highest weekly value within ±2 weeks of the tournament window |
| Pre-event baseline band | p25–p75 of weeks −26 to −6 relative to the peak |
| Burst ratio | Peak ÷ baseline median |
| Weeks to baseline | First week after the peak at or below the band's upper edge (p75) |

Percentiles rather than min–max: the WBC baseline window still overlaps the World
Cup (max = 36), which would inflate a min–max band into something meaningless.
The original 8-week definition was found to be contaminated the same way; the
corrected definition is documented as a post-hoc revision in
[`docs/decision-trail.md`](docs/decision-trail.md), with the pre-registered numbers
kept intact.

**Cross-check at daily resolution.** One event window was also pulled daily
(2022-11-01 → 2023-01-31). It shows that weekly aggregation hides single-day
spikes: the World Cup final (2022-12-18) reads **61** daily but only **9** in the
week containing it. Weekly therefore places the peak in the *opening* week, daily
in the *final*. Both charts ship — the disagreement is part of the result.

## Reproduce

Requires Python 3.13, `pandas`, `plotly`. No network access needed — all inputs are
snapshots under `data/raw/`.

```bash
pytest -q                                    # 14 tests over the metrics the results depend on
python scripts/analysis_weekly_main.py       # main result: the table below
python scripts/analysis_daily_vs_weekly.py   # weekly-smoothing check + baseline revision
python scripts/analysis_alignment.py         # peak-aligned vs end-aligned comparison
python scripts/make_drafts.py                # regenerate the charts (asserts as it builds)
python scripts/verify_drafts.py              # verify the written HTML, not the in-memory figure
```

`scripts/metrics.py` holds the four quantities the conclusions rest on
(`half_life`, `spike_ratio`, `periods_to_threshold`, `baseline_band`). They are
tested because each has a path that changes the answer without raising: a
half-life that is never reached returns `None` (not zero, and not "fast"), and a
spike ratio over an all-zero median returns `inf`. One test deliberately pins the
*breakdown point* of the baseline band — under roughly a quarter contamination the
p25–p75 window stops being robust, so the definition is not unconditionally safe
for events spaced closer together than these three.

`scripts/fetch_day*.py` hit the Google Trends API and **consume quota** — do not run
them without reading [`docs/prompt-verify-google-trends.md`](docs/prompt-verify-google-trends.md)
first. Everything else is offline.

`verify_drafts.py` parses the generated HTML and checks shape geometry, annotation
collisions at three container widths, overflow beyond the plot area, and that no
annotation refers to an element that does not exist. This exists because a silent
failure mode was hit once: `add_vrect`/`add_hline` default to
`exclude_empty_subplots=True` and discard shapes added to a subplot that has no
traces yet — no error, no warning.

## Results

| Tournament | Duration | Peak | Burst ratio | Baseline band | Weeks to baseline |
|---|---|---|---|---|---|
| 2022 FIFA World Cup | 4.0 wk | 36 | 36.0× | 1–2 | 5 |
| 2023 WBC (Taiwan games) | 0.6 wk | 32 | 16.0× | 1–2 | 3 |
| 2024 Paris Olympics | 2.3 wk | 46 | 23.0× | 2–3 | 3 |

Normalized decay (peak = 1.000):

| Weeks after peak | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| World Cup | 1.000 | 0.694 | 0.472 | 0.194 | 0.250 | 0.056 |
| WBC | 1.000 | 0.344 | 0.125 | 0.062 | 0.062 | 0.062 |
| Paris Olympics | 1.000 | 0.761 | 0.087 | 0.065 | 0.065 | 0.065 |

Charts: [`drafts/`](drafts/) — `draft-a-small-multiples.html` (primary),
`draft-c-daily-vs-weekly.html` (method). `draft-b-overlay.html` is a rejected
alternative kept for comparison and is **not** part of the deliverable.

## Limitations

Read these before the numbers. They are not caveats bolted on at the end — several
of them shaped the design.

1. **Search interest is not subscriptions.** Someone may subscribe during a
   tournament, never cancel, and simply stop searching. "Stopped searching" and
   "churned" are different events and this data cannot separate them. This is the
   single most likely misreading of the result.
2. **The detection floor depends on the baseline value and is not one number.**
   Weekly values in the baseline region are integers in the 1–3 range, so the
   smallest visible lift is: baseline 3 → **+33%**, baseline 2 → **+50%**,
   baseline 1 (World Cup) → **+100%**. Anything smaller is invisible. Reported
   per event, never as a single figure.
3. **n = 3, and sport type is fully confounded with tournament length.** WBC decays
   fastest — that may be because baseball interest is short-lived, or simply
   because Taiwan's games lasted one week. This data cannot separate the two, so
   every conclusion here is descriptive, not causal.
4. **Collection is not reproducible and the variance is unquantified.** Each Google
   Trends query re-samples and re-normalizes; historical values are *not* frozen.
   The snapshot under `data/raw/` freezes an unstable source — that is the reason
   it exists, not a claim that the data is stable. The reproducibility test was
   blocked by quota (see below).
5. **Event dates were not verified against primary sources**, and the correspondence
   between peaks and tournaments is *date alignment, not attribution*. Whether
   Chunghwa Telecom held broadcast rights for any of these events was not checked.
6. **Only the World Cup window has daily data.** The WBC and Olympic windows were
   never retrieved.

**Why several checks are missing.** Google Trends rate-limiting is a triggered
block, not per-minute throttling: 41% success in the first 14 minutes, then 0/30
across 47.5 hours, with backoff and idle cooldown both ineffective. Four planned
verifications (reproducibility, a `中華電信 MOD` control, event keywords, and the
two missing daily windows) remain unrun. Each was checked against "does this block
delivery?" — none do. The full attempt log is in
[`logs/quota_attempts.csv`](logs/quota_attempts.csv).

## Repository layout

```
data/raw/     Google Trends snapshots (CSV) + collection timestamp
logs/         append-only log of every API attempt, successful or not
scripts/      analysis, chart generation, verification, and (quota-consuming) fetch
tests/        pytest suite over scripts/metrics.py, including a real-data regression lock
drafts/       chart drafts; plotly.min.js is vendored so they open offline
docs/         project rules, decision trail, and the outstanding verification spec
```

`docs/` is written in Traditional Chinese — it is the working record for the author,
not part of the public deliverable.
