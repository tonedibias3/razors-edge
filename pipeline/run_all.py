"""One command to refresh everything:  python pipeline/run_all.py
Downloads the latest data, rebuilds the projections, and writes site/index.html."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(os.path.dirname(HERE), "work")
os.makedirs(WORK, exist_ok=True)


def run(script, cwd=WORK):
    print(f"\n=== {script} ===", flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(r.stdout, flush=True)
    if r.returncode:
        tail = (r.stdout or "")[-900:].replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::error title={script} failed::{tail}", flush=True)
        sys.exit(f"{script} failed")


run("fetch.py")
for s in ["prep_data.py", "college.py", "cfbstats.py", "draft.py", "odds.py", "weather.py", "injuries.py", "dk.py", "backtest.py", "finalize.py", "dvp_table.py", "logs.py"]:
    run(s)
run("build_page.py")
t = subprocess.run(["node", os.path.join(os.path.dirname(HERE), "tests", "smoke_test.js")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
print(t.stdout, flush=True)
if t.returncode:
    tail = (t.stdout or "")[-900:].replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::error title=smoke test failed::{tail}", flush=True)
    sys.exit("smoke test failed")
print("\nDone. The finished page is site/index.html")
