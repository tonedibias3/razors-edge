"""One command to refresh everything:  python pipeline/run_all.py
Downloads the latest data, rebuilds the projections, and writes site/index.html."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(os.path.dirname(HERE), "work")
os.makedirs(WORK, exist_ok=True)


def run(script, cwd=WORK):
    print(f"\n=== {script} ===", flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, script)], cwd=cwd)
    if r.returncode:
        sys.exit(f"{script} failed")


run("fetch.py")
for s in ["prep_data.py", "college.py", "odds.py", "dk.py", "backtest.py", "finalize.py", "dvp_table.py", "logs.py"]:
    run(s)
run("build_page.py")
subprocess.run(["node", os.path.join(os.path.dirname(HERE), "tests", "smoke_test.js")], check=True)
print("\nDone. The finished page is site/index.html")
