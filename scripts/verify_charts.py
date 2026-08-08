# -*- coding: utf-8 -*-
"""驗證『實際寫出的 HTML 檔』——不是記憶體裡的 figure。
解析 Plotly.newPlot(...) 的 layout JSON，檢查 shapes 存在、幾何正確、註記不指涉不存在的元素。
"""
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]   # repo 根目錄，腳本可隨 repo 搬移
import base64, json, re, struct, sys
from datetime import datetime
from pathlib import Path

D = REPO / "charts"
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
data, lay, txt = layout_of(D / "decay-by-event.html")
shapes = lay.get("shapes", [])
print(f"decay-by-event  traces={len(data)}  shapes={len(shapes)}")
if len(shapes) != 9:
    fails.append(f"decay-by-event shapes={len(shapes)}，應為 9")

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
        fails.append(f"decay-by-event 第 {i+1} 格賽程寬度 {g} != {w}")
if len(got) != 3:
    fails.append(f"decay-by-event 找到 {len(got)} 個賽程陰影，應為 3")

print("\n  基準帶（橫向 rect，xref 為 domain）與上緣實線：")
bands = [s for s in rects if str(s.get("xref", "")).endswith("domain")]
lines = [s for s in shapes if s.get("type") == "line"]
print(f"    基準帶 rect = {len(bands)} 個, 上緣 line = {len(lines)} 條")
if len(bands) != 3:
    fails.append(f"decay-by-event 基準帶 {len(bands)} 個，應為 3")
if len(lines) != 3:
    fails.append(f"decay-by-event 基準上緣線 {len(lines)} 條，應為 3")
for b, l in zip(bands, lines):
    if abs(b["y1"] - l["y0"]) > 1e-9:
        fails.append(f"decay-by-event 基準帶上緣 {b['y1']} 與實線 {l['y0']} 不吻合")

anns = [a.get("text", "") for a in lay.get("annotations", [])]
print(f"\n  註記 {len(anns)} 則。指涉陰影的註記：")
for a in anns:
    if "陰影" in a:
        print(f"    「{a}」→ 陰影 rect 存在：{len(got) == 3}")
        if len(got) != 3:
            fails.append("decay-by-event 有『陰影』註記但陰影不存在")
print(f"  「搜尋熱度 ≠ 訂閱數」出現 {sum('訂閱數' in a for a in anns)} 次（應為 3，每格一次）")
if sum("訂閱數" in a for a in anns) != 3:
    fails.append("decay-by-event 免責小字不是每格都有")

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
        if xr.startswith("paper") or a.get("x") is None:
            continue
        ax = lay[xr.replace("x", "xaxis").replace("axis1", "axis")]
        ay = lay[yr.replace("y", "yaxis").replace("axis1", "axis")]
        if "range" not in ax or "range" not in ay:
            continue
        d0, d1 = ax.get("domain", (0.0, 1.0))
        xlo, xhi = (_num(v) for v in ax["range"])
        ylo, yhi = (_num(v) for v in ay["range"])
        cx = (d0 + (_num(a["x"]) - xlo) / (xhi - xlo) * (d1 - d0)) * plot_w + a.get("xshift", 0)
        cy = (_num(a["y"]) - ylo) / (yhi - ylo) * plot_h + a.get("yshift", 0)
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


# ── 標註 vs 資料線 ────────────────────────────────────────────────────────
# 2026-08-08 補：原本只比對「標註 vs 標註」與「標註 vs 繪圖區邊界」，
# 完全沒有比對「標註 vs 資料線」。結果是免責小字被 x=-1→0 的陡升段整個穿過，
# 而驗證器一路回報「✔ 無碰撞」——**宣稱的檢查強度高於實際的檢查強度**。
# 這一類只能靠渲染截圖用眼睛發現，所以把它變成機器檢查。
def _num(v):
    """資料座標可能是數值或 ISO 日期字串（方法圖 的 x 軸是時間）。"""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("T", " ").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f"無法解析座標值：{v!r}")


# Plotly 6 會把 numpy／pandas 陣列序列化成 {"dtype": "f8", "bdata": "<base64>"}，
# 而不是純 JSON 陣列。主圖 的座標是 Python list（原樣輸出），
# 方法圖 的來自 pandas，就是這種二進位形式——不解碼會拿到字串 'dtype'。
_DTYPE = {"f8": "d", "f4": "f", "i8": "q", "i4": "i", "i2": "h", "i1": "b",
          "u8": "Q", "u4": "I", "u2": "H", "u1": "B"}


def _seq(v):
    """把 trace 的座標欄位轉成 Python list，處理 Plotly 的 base64 二進位編碼。"""
    if isinstance(v, dict) and "bdata" in v:
        code = _DTYPE.get(v.get("dtype"))
        if code is None:
            raise ValueError(f"未支援的 dtype：{v.get('dtype')}")
        raw = base64.b64decode(v["bdata"])
        n = len(raw) // struct.calcsize(code)
        return list(struct.unpack("<" + code * n, raw))
    return list(v)


def _seg_hits_box(p0, p1, box):
    """線段與矩形是否相交（Liang–Barsky 裁剪）。"""
    (x0, y0), (x1, y1) = p0, p1
    bx0, bx1, by0, by1 = box
    if max(x0, x1) < bx0 or min(x0, x1) > bx1:
        return False
    if max(y0, y1) < by0 or min(y0, y1) > by1:
        return False
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - bx0), (dx, bx1 - x0), (-dy, y0 - by0), (dy, by1 - y0)):
        if p == 0:
            if q < 0:
                return False
        else:
            r = q / p
            if p < 0:
                if r > t1:
                    return False
                t0 = max(t0, r)
            else:
                if r < t0:
                    return False
                t1 = min(t1, r)
    return t0 <= t1


def trace_polylines(lay, data, W):
    """把每條 trace 的資料點換成像素座標，座標系與 ann_boxes 相同（左下原點）。"""
    m = lay["margin"]
    plot_w, plot_h = W - m["l"] - m["r"], lay["height"] - m["t"] - m["b"]
    out = []
    for tr in data:
        if not tr.get("x") or not tr.get("y"):
            continue
        xr, yr = tr.get("xaxis", "x"), tr.get("yaxis", "y")
        ax = lay[xr.replace("x", "xaxis").replace("axis1", "axis")]
        ay = lay[yr.replace("y", "yaxis").replace("axis1", "axis")]
        # 單一座標軸的圖（方法圖）不會輸出 domain；未設 range 時也不會輸出 range。
        # domain 可安全預設為 [0,1]；range 缺失則無法精確定位，直接擋下——
        # 驗證工具不做近似，寧可要求產生端把 range 寫明。
        d0, d1 = ax.get("domain", (0.0, 1.0))
        if "range" not in ax or "range" not in ay:
            fails.append(f"{xr}/{yr} 未設定 range，無法做標註 vs 資料線檢查"
                         "（請在 make_charts.py 明確指定 range）")
            continue
        xlo, xhi = (_num(v) for v in ax["range"])
        ylo, yhi = (_num(v) for v in ay["range"])
        pts = []
        for xv, yv in zip(_seq(tr["x"]), _seq(tr["y"])):
            if xv is None or yv is None:
                continue
            px = (d0 + (_num(xv) - xlo) / (xhi - xlo) * (d1 - d0)) * plot_w
            py = (_num(yv) - ylo) / (yhi - ylo) * plot_h
            pts.append((px, py))
        out.append((xr, tr.get("name", "?"), pts))
    return out


def check_ann_vs_data(lay, data, label, widths=(900, 1100, 1400), pad=1.0):
    """標註文字方塊不得被任何資料線穿過。pad 是容差，避免擦邊誤報。"""
    print(f"\n  標註 vs 資料線（{label}）：")
    for W in widths:
        boxes = ann_boxes(lay, W)
        lines = trace_polylines(lay, data, W)
        hits = []
        for xr, text, x0, x1, y0, y1, _ in boxes:
            box = (x0 + pad, x1 - pad, y0 + pad, y1 - pad)
            if box[0] >= box[1] or box[2] >= box[3]:
                continue
            for lxr, name, pts in lines:
                if lxr != xr:
                    continue
                if any(_seg_hits_box(pts[i], pts[i + 1], box)
                       for i in range(len(pts) - 1)):
                    hits.append(f"「{text}」被資料線「{name}」（{xr}）穿過")
                    break
        print(f"    {W}px: " + ("✔ 無穿越" if not hits else "✘ " + " / ".join(hits)))
        fails.extend([f"{label} @{W}px: {h}" for h in hits])


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
    fails.extend([f"decay-by-event @{W}px: {h}" for h in hits + outside])

check_ann_vs_data(lay, data, "decay-by-event")

print("\n" + "=" * 70)
for name, exp_shapes in [("daily-vs-weekly.html", 0)]:
    d, l, t = layout_of(D / name)
    s = l.get("shapes", [])
    fills = [tr.get("fill") for tr in d if tr.get("fill")]
    print(f"{name}: traces={len(d)} shapes={len(s)} trace填色={fills}")
    if len(s) != exp_shapes:
        fails.append(f"{name} shapes={len(s)}，應為 {exp_shapes}")
    check_ann_vs_data(l, d, "daily-vs-weekly")

print("\n" + "=" * 70)
EXPECTED = {"decay-by-event.html", "daily-vs-weekly.html", "plotly.min.js"}
actual = {p.name for p in D.iterdir() if p.is_file()}
print(f"charts/ 內容：{sorted(actual)}")
if actual - EXPECTED:
    fails.append(f"charts/ 有非預期檔案：{sorted(actual - EXPECTED)}"
                 "（草稿 B 已於 2026-08-05 刪除，不得復活）")
if EXPECTED - actual:
    fails.append(f"charts/ 缺少：{sorted(EXPECTED - actual)}")

js = D / "plotly.min.js"
print(f"plotly.min.js 存在={js.exists()} 大小={js.stat().st_size if js.exists() else 0:,}")
for f in D.glob("*.html"):
    if 'src="plotly.min.js"' not in f.read_text(encoding="utf-8"):
        fails.append(f"{f.name} 未引用 plotly.min.js")

print("\n" + ("✘ 失敗：\n  " + "\n  ".join(fails) if fails else "✔ 全部通過"))
sys.exit(1 if fails else 0)
