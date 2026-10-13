"""在抓取新資料、覆蓋 listings_raw.json 之前執行，
把目前的 listings_raw.json 存成 listings_raw_prev.json（保留原本的擷取時間戳記），
report 才能正確比對新增物件。用法：python rotate_snapshot.py
"""
import pathlib, shutil, os, sys
sys.stdout.reconfigure(encoding="utf-8")

D = pathlib.Path(__file__).parent
cur = D / "listings_raw.json"
prev = D / "listings_raw_prev.json"

if not cur.exists():
    print("找不到 listings_raw.json，略過。")
else:
    mtime = cur.stat().st_mtime
    shutil.copy2(cur, prev)  # copy2 保留原始 mtime
    os.utime(prev, (mtime, mtime))
    print("已將 listings_raw.json（擷取時間戳記保留）備份為 listings_raw_prev.json")
