// Quick safety check run before every publish: if anything looks broken, the site is NOT updated.
const fs = require("fs"), path = require("path");
const root = path.join(__dirname, "..");
const core = require(path.join(root, "app", "core.js"));
const data = JSON.parse(fs.readFileSync(path.join(root, "work", "data.json"), "utf8"));
const dfs = JSON.parse(fs.readFileSync(path.join(root, "work", "dfs.json"), "utf8"));
const csv = fs.readFileSync(path.join(root, "app", "DKSalaries.csv"), "utf8").replace(/^﻿/, "");
let ok = true;
const t = (name, cond) => { console.log(cond ? "ok  " : "FAIL", name); if (!cond) ok = false; };
t("players loaded", data.players.length > 500);
t("schedule rows loaded", data.sched.length > 3000);
t("projection rows", dfs.rows.length > 200 && dfs.dst.length >= 20);
t("defense-vs-position table", ["QB", "RB", "WR", "TE"].every((p) => Object.keys(dfs.dvp[p] || {}).length >= 30));
t("game logs", Object.keys(dfs.logs).length > 300);
t("projections look sane", dfs.rows.every((r) => r[5] > -5 && r[5] < 60));
const dk = core.parseDK(csv);
t("salary file parses", !dk.error && dk.rows.length > 300);
if (!dk.error) {
  const pool = core.matchPool(dk.rows, dfs, {});
  t("most salaried players matched", pool.filter((p) => p.matched).length > 150);
  const r = core.optimizeLineup(pool.filter((p) => p.proj !== null), { cap: 50000, obj: "proj", excl: new Set() });
  t("a lineup can be built under the cap", r && !r.error && r.slots.length === 9 && r.slots.reduce((a, s) => a + s.p.salary, 0) <= 50000);
}
console.log(ok ? "SMOKE TEST PASSED" : "SMOKE TEST FAILED");
process.exit(ok ? 0 : 1);
