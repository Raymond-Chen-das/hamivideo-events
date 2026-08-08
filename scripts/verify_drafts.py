# -*- coding: utf-8 -*-
"""驗證『實際寫出的 HTML 檔』——不是記憶體裡的 figure。
解析 Plotly.newPlot(...) 的 layout JSON，檢查 shapes 存在、幾何正確、註記不指涉不存在的元素。
"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import json, re, sys
from pathlib import Path

D = REPO / "drafts"
fails = []


def layout_of(path):
    """用 raw_decode 逐段解析——正則的非貪婪比對會在巢狀大括號上斷掉。"""
    t = path.read_text(encoding="utf-8")
    m = re.search(r'Plotly\.newPlot\(\s*"[^"]+",\s*', t)
    if not m:
        fails.append(f"{path.name}: 找不到 Plotly.newPlot 呼叫")
        return None, None, t
    dec = json.JSONDecoder()
    data, end = dec.raw_decode(t, m.end())
    nxt = t.index("{", end)
    lay, _ = dec.raw_decode(t, nxt)
    return data, lay, t


print("=" * 70)
data, lay, txt = layout_of(D / "draft-a-small-multiples.html")
shapes = lay.get("shapes", [])
print(f"draft-A  traces={len(data)}  shapes={len(shapes)}")
if len(shapes) != 9:
    fails.append(f"draft-A shapes={len(shapes)}，應為 9")

rects = [s for s in shapes if s.get("type") == "rect"]
vr = [s for s in rects if s.get("y0") in (0, "0") or str(s.get("yref", "")).endswith("domain")]
print("\n  賽程陰影（直式 rect）寬度檢查——必須等比 4.0 / 0.57 / 2.29：")
want = [4.0, 0.571, 2.286]
got = []
for s in rects:
    if "x0" in s and isinstance(s["x0"], (int, float)) and str(s.get("yref", "")).endswith("domain"):
        got.append(round(s["x1"] - s["x0"], 3))
for i, (w, g) in enumerate(zip(want, got)):
    ok = abs(w - g) < 0.01
    print(f"    格 {i+1}: 期望 {w:>5} 實際 {g:>5}  {'✔' if ok else '�’✘'}")
    if not ok:
        fails.append(f"draft-A 第 {i+1} 格賽程寬度 {g} != {w}")
if len(got) != 3:
    fails.append(f"draft-A 找到 {len(got)} 個賽程陰影，應為 3")

print("\n  基準帶（橫向 rect，xref 為 domain）與上緣實線：")
bands = [s for s in rects if str(s.get("xref", "")).endswith("domain")]
lines = [s for s in shapes if s.get("type") == "line"]
print(f"    基準帶 rect = {len(bands)} 個, 上緣 line = {len(lines)} 條")
if len(bands) != 3:
    fails.append(f"draft-A 基準帶 {len(bands)} 個，應為 3")
if len(lines) != 3:
    fails.append(f"draft-A 基準上緣線 {len(lines)} 條，應為 3")
for b, l in zip(bands, lines):
    if abs(b["y1"] - l["y0"]) > 1e-9:
        fails.append(f"draft-A 基準帶上緣 {b['y1']} 與實線 {l['y0']} 不吻合")

anns = [a.get("text", "") for a in lay.get("annotations", [])]
print(f"\n  註記 {len(anns)} 則。指涉陰影的註記：")
for a in anns:
    if "陰影" in a:
        print(f"    「{a}」→ 陰影 rect 存在：{len(got) == 3}")
        if len(got) != 3:
            fails.append("draft-A 有『陰影』註記但陰影不存在")
print(f"  「搜尋熱度 ≠ 訂閱數」出現 {sum('訂閱數' in a for a in anns)} 次（應為 3，每格一次）")
if sum("訂閱數" in a for a in anns) != 3:
    fails.append("draft-A 免責小字不是每格都有")

# ── 標註碰撞：用幾何算，不靠眼睛 ────────────────────────────────────────────
def text_box(t, size):
    """估算文字方塊。CJK 約 1.0×字級，ASCII 約 0.52×。<b> 加約 4%。"""
    lines = re.sub(r"</?b>", "", t).split("<br>")
    bold = "<b>" in t
    w = max(sum(size * (1.0 if ord(ch) > 0x2E80 else 0.52) for ch in ln) for ln in lines)
    return w * (1.04 if bold else 1.0), len(lines) * size * 1.35


def ann_boxes(lay, W):
    """回傳 [(panel, text, x0,x1,y0,y1)]，像素座標，原點為繪圖區左下。"""
    m = lay["margin"]
    plot_w, plot_h = W - m["l"] - m["r"], lay["height"] - m["t"] - m["b"]
    out = []
    for a in lay.get("annotations", []):
        xr, yr = str(a.get("xref", "x")), str(a.get("yref", "y"))
        if xr.startswith("paper") or not isinstance(a.get("x"), (int, float)):
            continue
        ax = lay[xr.replace("x", "xaxis").replace("axis1", "axis")]
        ay = lay[yr.replace("y", "yaxis").replace("axis1", "axis")]
        d0, d1 = ax["domain"]
        xlo, xhi = ax["range"]; ylo, yhi = ay["range"]
        cx = (d0 + (a["x"] - xlo) / (xhi - xlo) * (d1 - d0)) * plot_w + a.get("xshift", 0)
        cy = (a["y"] - ylo) / (yhi - ylo) * plot_h + a.get("yshift", 0)
        # showarrow 時 x/y 是「箭頭指向的點」，文字在 (ax, ay) 偏移處。
        # Plotly 的 ay 以螢幕座標為準（正值向下），本函式用左下原點，故取負號。
        if a.get("showarrow"):
            cx += a.get("ax", 0)
            cy -= a.get("ay", 0)
        size = a.get("font", {}).get("size", 12)
        w, h = text_box(a.get("text", ""), size)
        anc = a.get("xanchor", "center")
        x0 = cx - w / 2 if anc in ("center", "auto") else (cx if anc == "left" else cx - w)
        yanc = a.get("yanchor", "middle")
        y0 = cy - h / 2 if yanc in ("middle", "auto") else (cy if yanc == "bottom" else cy - h)
        out.append((xr, a.get("text", ""), x0, x0 + w, y0, y0 + h, plot_h))
    return out


print("\n  標註碰撞檢測（多容器寬度）：")
for W in (900, 1100, 1400):
    boxes = ann_boxes(lay, W)
    hits = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if a[0] != b[0]:
                continue
            ox = min(a[3], b[3]) - max(a[2], b[2])
            oy = min(a[5], b[5]) - max(a[4], b[4])
            if ox > 0.5 and oy > 0.5:
                hits.append(f"「{a[1]}」×「{b[1]}」重疊 {ox:.1f}×{oy:.1f}px")
    outside = [f"「{b[1]}」 {b[4]:.1f}~{b[5]:.1f}px 超出 0~{b[6]:.0f}"
               for b in boxes if b[4] < -0.5 or b[5] > b[6] + 0.5]
    status = "✔ 無碰撞、無溢出" if not (hits or outside) else "✘ " + " / ".join(hits + outside)
    print(f"    {W}px: {status}")
    fails.extend([f"draft-A @{W}px: {h}" for h in hits + outside])

print("\n" + "=" * 70)
for name, exp_shapes in [("draft-c-daily-vs-weekly.html", 0)]:
    d, l, t = layout_of(D / name)
    s = l.get("shapes", [])
    fills = [tr.get("fill") for tr in d if tr.get("fill")]
    print(f"{name}: traces={len(d)} shapes={len(s)} trace填色={fills}")
    if len(s) != exp_shapes:
        fails.append(f"{name} shapes={len(s)}，應為 {exp_shapes}")

print("\n" + "=" * 70)
EXPECTED = {"draft-a-small-multiples.html", "draft-c-daily-vs-weekly.html", "plotly.min.js"}
actual = {p.name for p in D.iterdir() if p.is_file()}
print(f"drafts/ 內容：{sorted(actual)}")
if actual - EXPECTED:
    fails.append(f"drafts/ 有非預期檔案：{sorted(actual - EXPECTED)}"
                 "（草稿 B 已於 2026-08-05 刪除，不得復活）")
if EXPECTED - actual:
    fails.append(f"drafts/ 缺少：{sorted(EXPECTED - actual)}")

js = D / "plotly.min.js"
print(f"plotly.min.js 存在={js.exists()} 大小={js.stat().st_size if js.exists() else 0:,}")
for f in D.glob("draft-*.html"):
    if 'src="plotly.min.js"' not in f.read_text(encoding="utf-8"):
        fails.append(f"{f.name} 未引用 plotly.min.js")

print("\n" + ("✘ 失敗：\n  " + "\n  ".join(fails) if fails else "✔ 全部通過"))
sys.exit(1 if fails else 0)
