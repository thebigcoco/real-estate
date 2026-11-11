"""把歷次報告（archive/*.html + index.html）內嵌的物件資料串成「物件履歷」listing_history.json / .csv。
每戶記錄首次出現、每次調價、最後出現日期與狀態，之後可拿來和成交資料比對開價與成交價。
用法：python build_history.py（建完報告後執行；履歷只留在本機，不推到公開 repo）
"""
import csv, json, pathlib, re, sys
sys.stdout.reconfigure(encoding="utf-8")

D = pathlib.Path(__file__).parent


def load_versions():
    """回傳 [(擷取時間字串, 物件列表)]，依時間排序。同一擷取時間只取一份。"""
    seen, out = set(), []
    for f in list((D / "archive").glob("report_*.html")) + [D / "index.html"]:
        h = f.read_text(encoding="utf-8")
        t = re.search(r"擷取時間 (\d{4}-\d\d-\d\d \d\d:\d\d)", h)
        m = re.search(r"(?:const|var|let) DATA\s*=\s*(\[.*?\]);", h, re.S)
        if not (t and m) or t.group(1) in seen:
            continue
        seen.add(t.group(1))
        out.append((t.group(1), json.loads(m.group(1))))
    return sorted(out)


def unit_key(r):
    # 與 build_report.py 的合併規則一致：同區、同社區（無社區則同路）、同樓層、同坪數、同格局
    return (r["d"], r["c"] or r["r"], r.get("f"), r.get("ta"), r.get("ma"), r.get("l"))


def compatible(prev, r):
    """同一組 key 內再比屋齡（1 年內，屋齡會隨時間進位）、朝向、車位坪數。"""
    return (abs(prev["a"] - r["a"]) <= 1.0
            and (not prev.get("dr") or not r.get("dr") or prev["dr"] == r["dr"])
            and (not prev.get("ps") or not r.get("ps") or prev["ps"] == r["ps"]))


versions = load_versions()
tracks = {}  # key -> [track]
for when, rows in versions:
    taken = set()
    for r in rows:
        tl = tracks.setdefault(unit_key(r), [])
        for t in tl:
            if id(t) not in taken and compatible(t["last"], r):
                break
        else:
            t = {"key": unit_key(r), "obs": [], "last": None}
            tl.append(t)
        taken.add(id(t))
        t["obs"].append({"t": when, "p": r["p"], "pmax": r["pmax"], "i": r["i"], "n": r.get("n", 1)})
        t["last"] = r

latest = versions[-1][0]
first_version = versions[0][0]
units = []
for tl in tracks.values():
    for t in tl:
        o, r = t["obs"], t["last"]
        changes = [{"t": b["t"], "from": a["p"], "to": b["p"]} for a, b in zip(o, o[1:]) if a["p"] != b["p"]]
        seen_t = [x["t"] for x in o]
        all_t = [w for w, _ in versions]
        gaps = [w for w in all_t if seen_t[0] < w < seen_t[-1] and w not in seen_t]
        units.append({
            "district": r["d"], "community": r["c"], "road": r["r"], "floor": r.get("f"),
            "totalArea": r["ta"], "mainArea": r["ma"], "layout": r["l"], "age": r["a"],
            "firstSeen": seen_t[0], "firstSeenExact": seen_t[0] != first_version,  # 最早一版已在架上者，實際上架日更早
            "lastSeen": seen_t[-1], "status": "上架中" if seen_t[-1] == latest else "已下架",
            "firstPrice": o[0]["p"], "lastPrice": o[-1]["p"], "priceChanges": changes,
            "gaps": gaps, "listingIds": sorted({x["i"] for x in o}), "title": r["t"], "obs": o,
        })
units.sort(key=lambda u: (u["status"], u["district"], u["community"] or u["road"], u["floor"] or ""))

(D / "listing_history.json").write_text(
    json.dumps({"versions": [w for w, _ in versions], "units": units}, ensure_ascii=False, indent=1), encoding="utf-8")
with (D / "listing_history.csv").open("w", encoding="utf-8-sig", newline="") as fh:  # utf-8-sig 讓 Excel 直接開啟不亂碼
    w = csv.writer(fh)
    w.writerow(["區", "社區", "路段", "樓層", "建坪", "主建物", "格局", "屋齡", "首次出現", "首次出現為確切日期",
                "最後出現", "狀態", "首次開價(萬)", "最近開價(萬)", "調價次數", "調價紀錄", "中斷再出現"])
    for u in units:
        w.writerow([u["district"], u["community"], u["road"], u["floor"], u["totalArea"], u["mainArea"], u["layout"],
                    u["age"], u["firstSeen"], "是" if u["firstSeenExact"] else "否(最早一版已在架)", u["lastSeen"],
                    u["status"], u["firstPrice"], u["lastPrice"], len(u["priceChanges"]),
                    "；".join(f'{c["t"][:10]} {c["from"]}→{c["to"]}' for c in u["priceChanges"]),
                    "、".join(x[:10] for x in u["gaps"])])

act = sum(u["status"] == "上架中" for u in units)
print("版本", len(versions), [w for w, _ in versions])
print("物件", len(units), "上架中", act, "已下架", len(units) - act,
      "有調價", sum(bool(u["priceChanges"]) for u in units), "曾中斷再出現", sum(bool(u["gaps"]) for u in units))
