"""Assemble the finished page (site/index.html) from the template, the logic, the weekly data and the salary file."""
import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
from config import ROOT, WORK

rd = lambda *p: open(os.path.join(*p), encoding="utf-8-sig").read()
tpl, core = rd(ROOT, "app", "template.html"), rd(ROOT, "app", "core.js")
data, dfs = rd(WORK, "data.json"), rd(WORK, "dfs.json")
json.loads(data); json.loads(dfs)  # fail early if either file is broken
dk = json.dumps(rd(ROOT, "app", "DKSalaries.csv")).replace("</", "<\\/")
html = tpl.replace("/*__DKDEFAULT__*/", dk).replace("/*__CORE__*/", core).replace("/*__DATA__*/", data).replace("/*__DFS__*/", dfs)
assert "/*__" not in html, "a placeholder was not filled"

# syntax check of the page script so a broken edit never goes live
js = re.findall(r"<script>(.*?)</script>", html, re.S)[0]
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
    f.write(js)
r = subprocess.run(["node", "--check", f.name], capture_output=True, text=True)
assert r.returncode == 0, r.stderr

out = os.path.join(ROOT, "site")
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)
print("site/index.html", round(len(html) / 1024), "KB")
