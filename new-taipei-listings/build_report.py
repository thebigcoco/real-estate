"""由 listings_raw.json 產生 index.html（資料為自包含，可直接開啟）。"""
import json, pathlib, re

D = pathlib.Path(__file__).parent
raw = json.loads((D / "listings_raw.json").read_text(encoding="utf-8"))
OK_USE = {"住家用", "集合住宅", "國民住宅"}
BAD_USE = re.compile("事務所|辦公|商業|工業|住商|住工|零售|店鋪")
TS_COMM = {"明日城御風", "佳鋐運", "文華閱", "武泰臻和", "坤滿楓江路華廈", "晶華城", "台北花園廣場", "一品特區"}
TS_ROAD = {"信華五街", "信華六街", "莊泰路", "楓江路", "全興路", "泰林路二段"}
XZ_EXCL_ROAD = {"龍安路", "民安西路", "中正路", "後港一路"}

def num(s):
    m = re.search(r"[\d.]+", (s or "").replace(",", ""))
    return float(m.group()) if m else None

def base_rule(x):
    """區域／車位／用途／屋齡的基本篩選，回傳排除原因或 None。"""
    if x.get("par") != "有車位":
        return "無車位"
    if BAD_USE.search((x.get("u") or "").strip()):
        return "用途非住宅"
    if x["d"] == "新莊" and (x["r"] in XZ_EXCL_ROAD or re.search("迴龍|輔大", x["t"])):
        return "新莊迴龍輔大"
    if x["d"] == "泰山" and not (x["c"] in TS_COMM or x.get("kw") or x["r"] in TS_ROAD):
        return "泰山非塭仔圳"
    return None

rows = []
base_dropped = {}
for x in raw:
    why = base_rule(x)
    if why:
        base_dropped[why] = base_dropped.get(why, 0) + 1
        continue
    age = num(x.get("ag")) if num(x.get("ag")) is not None else num(x.get("a0"))
    if "個月" in (x.get("a0") or "") or "個月" in (x.get("ag") or ""):
        age = round((age or 0) / 12, 2)  # 屋齡「約6個月」換算成年
    x["a"] = age if age is not None else 0
    rows.append(x)
print("基本篩選排除", base_dropped)

import re
def excluded(r):
    """回傳排除原因，None 表示保留。"""
    name = (r["c"] or "") + r["t"]
    if re.match(r"^(1房|開放式|1廳1衛)", r["l"]) or re.search(r"一房|1房|套房", r["t"]):
        return "一房屋型"
    if r["d"] in ("板橋", "新莊") and "超級城市" in name:
        return "超級城市"
    if r["d"] == "板橋" and "威尼斯" in name:
        return "威尼斯"
    if r["d"] == "土城" and re.search("金城舞|紅布朗", name):
        return "金城舞／紅布朗"
    if r["d"] == "土城" and r["r"] == "中央路三段" and "帝寶" in name:
        return "土城四季花園／大同莊園／世界花園／金城帝寶"  # 標題只寫「帝寶」的金城帝寶物件
    if r["d"] == "土城" and re.search("四季花園|大同莊園|世界花園|金城帝寶", name):
        return "土城四季花園／大同莊園／世界花園／金城帝寶"
    if r["d"] == "樹林" and (r["r"].startswith("學") or re.search("北大", name)):
        return "樹林北大"
    if r["d"] == "樹林" and r["r"].startswith(("佳園路", "柑園街", "大義路", "田尾街", "桃子腳路")):
        return "樹林佳園路／柑園街／大義路／田尾街／桃子腳路"
    return None

dropped = {}
kept = []
for r in rows:
    why = excluded(r)
    if why:
        dropped[why] = dropped.get(why, 0) + 1
    else:
        kept.append(r)
rows = kept
print("排除", dropped)

# 同一物件常被多位房仲重複刊登：同區、同社區（無社區則同路）、同樓層、同坪數、同格局、同屋齡、同車位、同朝向視為同一戶
groups = {}
for r in rows:
    k = (r["d"], r["c"] or r["r"], r.get("f"), r.get("ta"), r.get("ma"), r.get("l"))
    groups.setdefault(k, []).append(r)

def same_unit(a, b):
    """屋齡差 0.4 年內；朝向、車位坪數若兩邊都有寫則需相同。"""
    return (abs(a["a"] - b["a"]) <= 0.4
            and (not a.get("dr") or not b.get("dr") or a["dr"] == b["dr"])
            and (not a.get("ps") or not b.get("ps") or a["ps"] == b["ps"]))

merged = []
for g in groups.values():
    clusters = []
    for r in sorted(g, key=lambda x: x["a"]):
        for c in clusters:
            if same_unit(c[0], r):
                c.append(r)
                break
        else:
            clusters.append([r])
    for c in clusters:
        c.sort(key=lambda x: x["p"])  # 保留最低價的刊登
        best = c[0]
        best["n"] = len(c)
        best["pmax"] = c[-1]["p"] if c[-1]["p"] != best["p"] else None
        merged.append(best)
print("重複合併", len(rows), "->", len(merged))
rows = merged
for r in rows:
    if r["ta"] and (not r["up"] or abs(r["up"] - r["p"] / r["ta"]) > 0.25 * r["p"] / r["ta"]):
        r["up"] = round(r["p"] / r["ta"], 2)  # 樂屋單價欄位偶有錯誤，改以總價/總建坪重算
    r["ok"] = 1 if r["u"] in OK_USE else 0  # 1=用途確認為住宅；0=用途未載明

import datetime
# 擷取時間 = 原始資料檔的寫入時間（台灣時間）
fetched = datetime.datetime.fromtimestamp((D / "listings_raw.json").stat().st_mtime).strftime("%Y-%m-%d %H:%M")
TEMPLATE = (D / "report_template.html").read_text(encoding="utf-8")
html = TEMPLATE.replace("{{FETCHED}}", fetched).replace("/*DATA*/[]", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))
(D / "index.html").write_text(html, encoding="utf-8")
print("rows", len(rows), "verified", sum(r["ok"] for r in rows))
