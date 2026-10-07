// Hit-rate math. Inlined into the page by build_page.py and also tested in Node.
// A game row is: [season, week, stype(0 reg/1 post), team, opp, home, passYds, passTd,
//                 rushYds, recYds, rec, attempts, carries, targets]
const STATS = {
  pass_yds: { label: "Passing yards",   idx: 6,  useIdx: 11, useLabel: "Attempts", needsAtt: true },
  pass_td:  { label: "Passing TDs",     idx: 7,  useIdx: 11, useLabel: "Attempts", needsAtt: true },
  rush_yds: { label: "Rushing yards",   idx: 8,  useIdx: 12, useLabel: "Carries",  needsAtt: false },
  rec_yds:  { label: "Receiving yards", idx: 9,  useIdx: 13, useLabel: "Targets",  needsAtt: false },
  rec:      { label: "Receptions",      idx: 10, useIdx: 13, useLabel: "Targets",  needsAtt: false },
  any_td:   { label: "Anytime TD",      idx: 14, useIdx: 15, useLabel: "Carries + targets", needsAtt: false },
};
const POS_STATS = {
  QB: ["pass_yds", "pass_td", "rush_yds", "any_td"],
  RB: ["rush_yds", "rec_yds", "rec", "any_td"],
  WR: ["rec_yds", "rec", "any_td"],
  TE: ["rec_yds", "rec", "any_td"],
};

// Games that count for a stat. Passing stats need a pass attempt; the rest count any
// game with offensive involvement (the data file already drops games with none).
function getSample(games, statKey, regOnly) {
  const s = STATS[statKey];
  return games.filter((g) => (!regOnly || g[2] === 0) && (!s.needsAtt || g[11] > 0));
}

function median(a) {
  if (!a.length) return null;
  const b = [...a].sort((x, y) => x - y);
  const m = b.length >> 1;
  return b.length % 2 ? b[m] : (b[m - 1] + b[m]) / 2;
}

function summarize(games, idx, line) {
  const v = games.map((g) => g[idx]);
  let over = 0, under = 0, push = 0;
  for (const x of v) {
    if (x > line) over++;
    else if (x < line) under++;
    else push++;
  }
  const n = v.length;
  return { n, over, under, push, avg: n ? v.reduce((a, b) => a + b, 0) / n : null, median: median(v) };
}

// Put a median on a .5 like a sportsbook line.
function lineFromMedian(med, statKey) {
  if (med === null) return 0.5;
  if (statKey === "pass_td" || statKey === "rec" || statKey === "any_td") return Math.max(0.5, Math.round(med) - 0.5);
  return Math.floor(med) + 0.5;
}
// Player page: median of his last 10 games.
function defaultLine(sample, statKey) {
  return lineFromMedian(median(sample.slice(-10).map((g) => g[STATS[statKey].idx])), statKey);
}
// Defense page: median of every counted player-game in the chosen seasons.
function leagueLine(rows, statKey) {
  return lineFromMedian(median(rows.map((r) => r[STATS[statKey].idx])), statKey);
}

// ---- Defense view ----
// A defense row is: [season, week, stype, defense, pos, rank, passYds, passTd, rushYds, recYds,
//                    rec, playerName, offenseTeam, family]
// Stat columns 6-10 line up with the player game rows, so summarize() works on both.
// family: p = passing (ranked by attempts), r = rushing (carries), c = catching (targets).
const DEF_TOP = { QB: 1, RB: 2, WR: 3, TE: 1 };
const DEF_USE = { p: "attempts", r: "carries", c: "targets" };
function defFamily(pos, statKey) {
  if (statKey === "pass_yds" || statKey === "pass_td") return "p";
  if (statKey === "any_td") return pos === "QB" ? "p" : pos === "RB" ? "r" : "c";
  if (statKey === "rush_yds") return pos === "QB" ? "p" : "r";
  return "c";
}
function defSample(rows, pos, statKey, topN, minSeason, regOnly) {
  const fam = defFamily(pos, statKey);
  return rows.filter((r) => r[4] === pos && r[13] === fam && r[5] <= topN && r[0] >= minSeason && (!regOnly || r[2] === 0));
}
function byDefense(sample, idx, line) {
  const m = new Map();
  for (const r of sample) {
    const a = m.get(r[3]);
    if (a) a.push(r); else m.set(r[3], [r]);
  }
  return [...m.entries()].map(([def, g]) => ({ def, ...summarize(g, idx, line) }));
}

// ---- Matchup ----
// How a player is used: his typical rank on his offense (1 = top) over his last 10 ranked games.
// That tells the page whether to compare him with WR1s, the top 2 WRs, and so on.
function roleTop(defRows, name, pos, statKey) {
  const fam = defFamily(pos, statKey);
  const mine = defRows.filter((r) => r[11] === name && r[4] === pos && r[13] === fam);
  mine.sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const med = median(mine.slice(-10).map((r) => r[5]));
  return med === null ? DEF_TOP[pos] : Math.min(DEF_TOP[pos], Math.max(1, Math.ceil(med)));
}

// Probability a bet must win to break even, from American odds (-115 -> 0.535, +150 -> 0.4).
function breakEven(odds) {
  if (!Number.isFinite(odds) || Math.abs(odds) < 100) return null;
  return odds < 0 ? -odds / (-odds + 100) : 100 / (odds + 100);
}

// Rough combined estimate: the player's rate, shifted by how far this defense sits from the league.
// player, defn, league are summarize() results. err is one typical standard error of the two rates.
function matchupEstimate(player, defn, league) {
  if (!player.n || !defn.n || !league.n) return null;
  const p = player.over / player.n, d = defn.over / defn.n, l = league.over / league.n;
  const se = (x, n) => { const q = (x + 0.5) / (n + 1); return Math.sqrt((q * (1 - q)) / (n + 1)); };
  const err = Math.sqrt(se(player.over, player.n) ** 2 + se(defn.over, defn.n) ** 2);
  return { p, d, l, gap: d - l, est: Math.min(1, Math.max(0, p + (d - l))), err };
}

// ---- Top hit rates ----
// entries: [{id, name, pos, team, games, line}]. ctx: {def, next, season}. o: {stat, reg, win, sort}.
// Each row: his hit rate over the last `win` games on his line, his last 5, average, next opponent,
// how often that defense lets his role clear the same line (last 3 seasons), and the combined estimate.
function rankEntries(entries, ctx, o) {
  const s = STATS[o.stat];
  const roleCache = new Map(), defCache = new Map();
  const rows = [];
  for (const e of entries) {
    const smp = getSample(e.games, o.stat, o.reg);
    if (smp.length < o.win) continue;
    const r = summarize(smp.slice(-o.win), s.idx, e.line);
    const r5 = summarize(smp.slice(-5), s.idx, e.line);
    const nx = (ctx.next && ctx.next[e.team]) || null;
    let allows = null, est = null;
    if (nx) {
      let top = roleCache.get(e.id);
      if (top === undefined) { top = roleTop(ctx.def, e.name, e.pos, o.stat); roleCache.set(e.id, top); }
      const key = `${e.pos}|${top}|${e.line}`;
      let c = defCache.get(key);
      if (!c) {
        const all = defSample(ctx.def, e.pos, o.stat, top, ctx.season - 2, o.reg);
        c = { lg: summarize(all, s.idx, e.line), m: new Map(byDefense(all, s.idx, e.line).map((x) => [x.def, x])) };
        defCache.set(key, c);
      }
      const dm = c.m.get(nx.opp);
      if (dm) {
        allows = dm.over / dm.n;
        const m = matchupEstimate(r, dm, c.lg);
        if (m) est = Math.min(100, Math.max(0, Math.round(m.p * 100) + (Math.round(m.d * 100) - Math.round(m.l * 100))));
      }
    }
    rows.push({ id: e.id, name: e.name, pos: e.pos, team: e.team, line: e.line, n: r.n, over: r.over,
                hit: r.over / r.n, avg: r.avg, over5: r5.over, n5: r5.n, nx, allows, est });
  }
  const by = {
    hit: (a, b) => b.hit - a.hit || b.avg - a.avg,
    avg: (a, b) => b.avg - a.avg || b.hit - a.hit,
    est: (a, b) => (b.est === null ? -1 : b.est) - (a.est === null ? -1 : a.est) || b.hit - a.hit,
  };
  return rows.sort(by[o.sort] || by.hit);
}

// Pasted sportsbook lines: "Name 74.5", "Name, 74.5", "Name o74.5", "Name 74.5 (-115)".
// lookup(normalizedName) returns a player or undefined.
function parseLines(text, lookup) {
  const entries = [], missing = [];
  for (const raw of text.split(/\n+/)) {
    const t = raw.replace(/\(.*?\)/g, " ").trim();
    if (!t) continue;
    const m = t.match(/^(.+?)[\s,;:|\t]+(?:over|under|o|u)?\s*(\d+(?:\.\d+)?)\s*$/i);
    if (!m) { missing.push(raw.trim()); continue; }
    const p = lookup(m[1].toLowerCase().replace(/[^a-z0-9]/g, ""));
    if (!p) { missing.push(m[1].trim()); continue; }
    entries.push({ p, line: parseFloat(m[2]) });
  }
  return { entries, missing };
}

// ---- DFS (DraftKings classic) ----
const DK_TEAM = { JAC: "JAX", LAR: "LA", WSH: "WAS", ARZ: "ARI", BLT: "BAL", CLV: "CLE", HST: "HOU", LVR: "LV", NOR: "NO", NWE: "NE", GNB: "GB", KAN: "KC", SFO: "SF", TAM: "TB", SDG: "LAC" };
const dkTeam = (t) => { const u = String(t || "").trim().toUpperCase(); return DK_TEAM[u] || u; };
function dkNorm(name) {
  return String(name).toLowerCase().replace(/\b(jr|sr|ii|iii|iv|v)\b/g, " ").replace(/[^a-z0-9]/g, "");
}
function parseCSV(text) {
  const rows = [];
  let row = [], cur = "", q = false;
  text = String(text).replace(/^﻿/, "");
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) {
      if (ch === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += ch;
    } else if (ch === '"') q = true;
    else if (ch === ",") { row.push(cur); cur = ""; }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cur); cur = "";
      if (row.some((x) => x.trim() !== "")) rows.push(row);
      row = [];
    } else cur += ch;
  }
  row.push(cur);
  if (row.some((x) => x.trim() !== "")) rows.push(row);
  return rows;
}
// DraftKings "Export to CSV" file -> [{id, name, pos, team, opp, game, salary, fppg, status}]
function parseDK(text) {
  const t = parseCSV(text);
  if (t.length < 2) return { rows: [], error: "That doesn't look like a DraftKings salary file." };
  const head = t[0].map((h) => h.trim().toLowerCase());
  const col = (n) => head.indexOf(n);
  const iPos = col("position"), iSal = col("salary"), iTeam = col("teamabbrev"), iGame = col("game info"), iFp = col("avgpointspergame"), iSt = col("status"), iId = col("id");
  let iName = col("name");
  const iNI = col("name + id");
  if (iName < 0 && iNI < 0) return { rows: [], error: "Couldn't find the player name column." };
  if (iPos < 0 || iSal < 0 || iTeam < 0) return { rows: [], error: "Couldn't find the Position, Salary or TeamAbbrev columns." };
  const rows = [];
  for (const r of t.slice(1)) {
    const name = (iName >= 0 ? r[iName] : r[iNI].replace(/\s*\(\d+\)\s*$/, "")).trim();
    const salary = parseFloat(r[iSal]);
    if (!name || !Number.isFinite(salary)) continue;
    const team = dkTeam(r[iTeam]);
    let opp = "", game = "";
    const m = iGame >= 0 && String(r[iGame]).match(/^([A-Za-z]+)@([A-Za-z]+)/);
    if (m) { const a = dkTeam(m[1]), h = dkTeam(m[2]); game = a + "@" + h; opp = team === a ? h : a; }
    const fp = iFp >= 0 ? parseFloat(r[iFp]) : NaN;
    rows.push({ id: iId >= 0 ? r[iId] : name, name, pos: r[iPos].trim().toUpperCase(), team, opp, game, salary, fppg: Number.isFinite(fp) ? fp : null, status: iSt >= 0 ? (r[iSt] || "").trim().toUpperCase() : "" });
  }
  return { rows, error: rows.length ? null : "No players found in that file." };
}
// proj: {rows: [[name,pos,team,opp,home,proj,floor,ceil,ewma,adj,implied,dvp,basic]], dst: [[team,opp,proj,ewma]]}
function matchPool(dk, proj, overrides) {
  const byNameTeam = new Map(), byName = new Map(), dst = new Map();
  for (const r of proj.rows) {
    const k = dkNorm(r[0]);
    byNameTeam.set(k + "|" + r[2], r);
    (byName.get(k) || byName.set(k, []).get(k)).push(r);
  }
  for (const d of proj.dst) dst.set(d[0], d);
  return dk.map((p) => {
    const o = { ...p, proj: null, floor: null, ceil: null, ewma: null, adj: null, basic: 0, matched: false };
    if (p.pos === "DST") {
      const d = dst.get(p.team);
      o.logKey = "DST|" + p.team;
      if (d) { o.proj = d[2]; o.floor = Math.max(0, Math.round((d[2] - 4) * 10) / 10); o.ceil = Math.round((d[2] + 6) * 10) / 10; o.ewma = d[3]; o.basic = 1; o.matched = true; }
    } else {
      const k = dkNorm(p.name);
      let r = byNameTeam.get(k + "|" + p.team);
      if (!r) { const c = (byName.get(k) || []).filter((x) => x[1] === p.pos); if (c.length === 1) r = c[0]; }
      if (r) { o.logKey = r[0] + "|" + r[2]; o.proj = r[5]; o.floor = r[6]; o.ceil = r[7]; o.ewma = r[8]; o.adj = r[9]; o.basic = r[12]; o.matched = true; }
    }
    const ov = overrides && overrides[o.id];
    if (ov !== undefined && Number.isFinite(ov)) { o.base = o.proj; o.proj = ov; o.floor = Math.max(0, Math.round((ov * 0.6) * 10) / 10); o.ceil = Math.round(ov * 1.5 * 10) / 10; o.edited = true; }
    o.value = o.proj !== null && p.salary > 0 ? o.proj / (p.salary / 1000) : null;
    return o;
  });
}

// Best lineup under the salary cap: QB, 2 RB, 3 WR, TE, FLEX (RB/WR/TE), DST.
// solveBase: no stack rules. pool rows need {id,pos,salary,game,team,<obj>}.
// o: {cap, obj:'proj'|'floor', locks:Set (forced in), excl:Set, noTeFlex:bool}
function solveBase(pool, o) {
  const cap = Math.round((o.cap || 50000) / 100), obj = o.obj || "proj";
  const locks = o.locks || new Set(), excl = o.excl || new Set();
  const BONUS = 10000, NEG = -1e15;
  const cand = pool.filter((p) => p[obj] !== null && p[obj] !== undefined && p.salary > 0 && (!excl.has(p.id) || locks.has(p.id)));
  const byPos = { QB: [], RB: [], WR: [], TE: [], DST: [] };
  for (const p of cand) if (byPos[p.pos]) byPos[p.pos].push(p);
  const val = (p) => p[obj] + (locks.has(p.id) ? BONUS : 0);

  function groupDP(items, k) {
    const n = items.length;
    if (k === 0) { const G = new Array(cap + 1).fill(NEG); G[0] = 0; return { G, pick: () => [] }; }
    const dp = Array.from({ length: k + 1 }, () => new Float64Array(cap + 1).fill(NEG));
    dp[0][0] = 0;
    const take = Array.from({ length: n }, () => Array.from({ length: k + 1 }, () => new Uint8Array(cap + 1)));
    for (let i = 0; i < n; i++) {
      const s = Math.round(items[i].salary / 100), v = val(items[i]);
      for (let j = Math.min(k, i + 1); j >= 1; j--)
        for (let u = cap; u >= s; u--) {
          const prev = dp[j - 1][u - s];
          if (prev > NEG / 2 && prev + v > dp[j][u]) { dp[j][u] = prev + v; take[i][j][u] = 1; }
        }
    }
    return {
      G: Array.from(dp[k]),
      pick(u) {
        const out = []; let j = k;
        for (let i = n - 1; i >= 0 && j > 0; i--) if (take[i][j][u]) { out.push(items[i]); j--; u -= Math.round(items[i].salary / 100); }
        return out;
      },
    };
  }

  let best = null;
  for (const flex of ["RB", "WR", "TE"]) {
    if (flex === "TE" && o.noTeFlex) continue;
    const need = { QB: 1, RB: 2 + (flex === "RB"), WR: 3 + (flex === "WR"), TE: 1 + (flex === "TE"), DST: 1 };
    const order = ["QB", "RB", "WR", "TE", "DST"];
    const groups = order.map((g) => groupDP(byPos[g], need[g]));
    let C = new Array(cap + 1).fill(NEG); C[0] = 0;
    const args = [];
    for (const g of groups) {
      const N = new Array(cap + 1).fill(NEG), A = new Int32Array(cap + 1).fill(-1);
      for (let s = 0; s <= cap; s++) {
        if (C[s] <= NEG / 2) continue;
        for (let u = 0; s + u <= cap; u++) {
          if (g.G[u] <= NEG / 2) continue;
          const t = C[s] + g.G[u];
          if (t > N[s + u]) { N[s + u] = t; A[s + u] = u; }
        }
      }
      C = N; args.push(A);
    }
    let bs = -1, bv = NEG;
    for (let s = 0; s <= cap; s++) if (C[s] > bv) { bv = C[s]; bs = s; }
    if (bs < 0 || bv <= NEG / 2) continue;
    if (!best || bv > best.v) {
      const picks = {}; let s = bs;
      for (let gi = order.length - 1; gi >= 0; gi--) { const u = args[gi][s]; picks[order[gi]] = groups[gi].pick(u); s -= u; }
      best = { v: bv, flex, picks };
    }
  }
  if (!best) return null;
  const sortBy = (a) => a.slice().sort((x, y) => y[obj] - x[obj]);
  const rb = sortBy(best.picks.RB), wr = sortBy(best.picks.WR), te = sortBy(best.picks.TE);
  const slots = [{ slot: "QB", p: best.picks.QB[0] }, { slot: "RB", p: rb[0] }, { slot: "RB", p: rb[1] },
    { slot: "WR", p: wr[0] }, { slot: "WR", p: wr[1] }, { slot: "WR", p: wr[2] }, { slot: "TE", p: te[0] }];
  const fl = best.flex === "RB" ? rb[2] : best.flex === "WR" ? wr[3] : te[1];
  slots.push({ slot: "FLEX", p: fl }, { slot: "DST", p: best.picks.DST[0] });
  const ps = slots.map((s) => s.p);
  for (const id of locks) if (cand.some((p) => p.id === id) && !ps.some((p) => p.id === id)) return { error: "Your picks don't fit under the cap together." };
  const sum = (f) => Math.round(ps.reduce((a, p) => a + (p[f] || 0), 0) * 10) / 10;
  return { slots, salary: ps.reduce((a, p) => a + p.salary, 0), proj: sum("proj"), floor: sum("floor"), v: ps.reduce((a, p) => a + p[obj], 0), games: new Set(ps.map((p) => p.game || p.team)).size };
}

// With rules: o also takes stack (WR/TE partners with the QB), bring (players from the other team in his game), stackTeam, maxGame, maxTeam (0 = no limit), maxDst (salary cap on the defense).
// Exact: when a solution has too many players from one game/team, split into "drop one of them" cases and search best-first.
function optimizeLineup(pool, o) {
  o = o || {};
  const maxG = o.maxGame || 99, maxT = o.maxTeam || 99;
  const cands = pool.filter((p) => !(p.pos === "DST" && o.maxDst && p.salary > o.maxDst));
  const locks0 = new Set(o.locks || []), excl0 = new Set(o.excl || []);
  const needS = o.stack || 0, needB = o.bring || 0, obj = o.obj || "proj";
  if (o.stackTeam) for (const p of cands) if (p.pos === "QB" && p.team !== o.stackTeam && !locks0.has(p.id)) excl0.add(p.id);
  const mk = (excl, locks) => solveBase(cands, { cap: o.cap, obj: o.obj, noTeFlex: o.noTeFlex, excl, locks });
  const violation = (sol) => {
    const by = (key, lim, skipDst) => {
      const m = new Map();
      for (const s of sol.slots) { if (skipDst && s.p.pos === "DST") continue; const k = key(s.p); (m.get(k) || m.set(k, []).get(k)).push(s.p); }
      for (const a of m.values()) if (a.length > lim) return a;
      return null;
    };
    return by((p) => p.game || p.team, maxG, false) || by((p) => p.team, maxT, true);
  };
  const root = mk(excl0, locks0);
  if (!root || root.error) return root;
  const heap = [{ sol: root, excl: excl0, locks: locks0 }];
  for (let n = 0; heap.length && n < 1500; n++) {
    heap.sort((a, b) => b.sol.v - a.sol.v);
    const node = heap.shift();
    // Stack rules, judged against the QB in this lineup: first settle the QB, then add partners one at a time.
    const qb = (needS || needB) && node.sol.slots[0].p;
    if (qb) {
      const inSol = node.sol.slots.map((s) => s.p);
      const mates = inSol.filter((p) => (p.pos === "WR" || p.pos === "TE") && p.team === qb.team).length;
      const backs = inSol.filter((p) => p.pos !== "QB" && p.pos !== "DST" && qb.game && p.game === qb.game && p.team !== qb.team).length;
      const need = !node.locks.has(qb.id) || mates < needS || backs < needB;
      if (need) {
        if (!node.locks.has(qb.id)) {
          const ex = new Set(node.excl); ex.add(qb.id);
          const s1 = mk(ex, node.locks); if (s1 && !s1.error) heap.push({ sol: s1, excl: ex, locks: node.locks });
          const lk = new Set(node.locks); lk.add(qb.id);
          heap.push({ sol: node.sol, excl: node.excl, locks: lk });
          continue;
        }
        const want = mates < needS ? (p) => (p.pos === "WR" || p.pos === "TE") && p.team === qb.team : (p) => p.pos !== "QB" && p.pos !== "DST" && qb.game && p.game === qb.game && p.team !== qb.team;
        const opts = cands.filter((p) => want(p) && !node.locks.has(p.id) && !node.excl.has(p) && !node.excl.has(p.id) && p[obj] !== null && p[obj] !== undefined).sort((a, b) => b[obj] - a[obj]);
        const ex = new Set(node.excl);
        for (const c of opts) {
          const lk = new Set(node.locks); lk.add(c.id);
          const sj = mk(ex, lk);
          if (sj && !sj.error) heap.push({ sol: sj, excl: new Set(ex), locks: lk });
          ex.add(c.id);
        }
        continue;
      }
    }
    const g = violation(node.sol);
    if (!g) return node.sol;
    const keep = [];
    for (const p of g) {
      if (node.locks.has(p.id)) { keep.push(p); continue; }
      const ex = new Set(node.excl); ex.add(p.id);
      const lk = new Set(node.locks); for (const q of keep) lk.add(q.id);
      const s = mk(ex, lk);
      if (s && !s.error) heap.push({ sol: s, excl: ex, locks: lk });
      keep.push(p);
    }
  }
  return { error: "Couldn't find a lineup that follows all of your rules. Loosen one." };
}

const TEAM_NAMES = {
  ARI: "Arizona Cardinals", ATL: "Atlanta Falcons", BAL: "Baltimore Ravens", BUF: "Buffalo Bills",
  CAR: "Carolina Panthers", CHI: "Chicago Bears", CIN: "Cincinnati Bengals", CLE: "Cleveland Browns",
  DAL: "Dallas Cowboys", DEN: "Denver Broncos", DET: "Detroit Lions", GB: "Green Bay Packers",
  HOU: "Houston Texans", IND: "Indianapolis Colts", JAX: "Jacksonville Jaguars", KC: "Kansas City Chiefs",
  LA: "Los Angeles Rams", LAC: "Los Angeles Chargers", LV: "Las Vegas Raiders", MIA: "Miami Dolphins",
  MIN: "Minnesota Vikings", NE: "New England Patriots", NO: "New Orleans Saints", NYG: "New York Giants",
  NYJ: "New York Jets", PHI: "Philadelphia Eagles", PIT: "Pittsburgh Steelers", SEA: "Seattle Seahawks",
  SF: "San Francisco 49ers", TB: "Tampa Bay Buccaneers", TEN: "Tennessee Titans", WAS: "Washington Commanders",
};

// Team colors: [background, text]. Used for the small team tags.
const TEAM_COLORS = {
  ARI:["#97233F","#fff"],ATL:["#A71930","#fff"],BAL:["#241773","#fff"],BUF:["#00338D","#fff"],CAR:["#0085CA","#fff"],CHI:["#0B162A","#fff"],
  CIN:["#FB4F14","#fff"],CLE:["#FF3C00","#fff"],DAL:["#003594","#fff"],DEN:["#002244","#fff"],DET:["#0076B6","#fff"],GB:["#203731","#FFB612"],
  HOU:["#03202F","#fff"],IND:["#002C5F","#fff"],JAX:["#006778","#fff"],KC:["#E31837","#fff"],LV:["#000000","#C4C8CB"],LAC:["#0080C6","#fff"],
  LA:["#003594","#FFD100"],MIA:["#008E97","#fff"],MIN:["#4F2683","#fff"],NE:["#002244","#fff"],NO:["#D3BC8D","#101820"],NYG:["#0B2265","#fff"],
  NYJ:["#125740","#fff"],PHI:["#004C54","#fff"],PIT:["#FFB612","#101820"],SEA:["#69BE28","#002244"],SF:["#AA0000","#fff"],TB:["#D50A0A","#fff"],
  TEN:["#4B92DB","#fff"],WAS:["#5A1414","#FFB612"]
};
function teamPill(t) {
  const k = dkTeam ? dkTeam(String(t || "")) : String(t || ""), c = TEAM_COLORS[k] || TEAM_COLORS[t];
  const s = String(t || "").replace(/[&<>"]/g, (x) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[x]));
  return c ? `<span class="tm" style="background:${c[0]};color:${c[1]}">${s}</span>` : `<span class="tm">${s}</span>`;
}

// ---- Teasers ----
// A schedule row is [season, week, date, away, home, homeMargin, homeSpread, total, awayScore, homeScore].
// homeSpread is how many points the home team is favored by. A team's own line is the opposite sign for
// the home team (favored by 3 = -3) and the same sign for the road team (home favored by 3 = road +3).
const KEY_MARGINS = [3, 7, 10, 14];
function teamGames(sched) {
  const out = [];
  for (const r of sched) {
    const [season, week, date, away, home, res, sp] = r;
    out.push({ season, week, date, team: home, opp: away, home: 1, line: sp === null ? null : -sp, margin: res, pf: r[9], pa: r[8] });
    out.push({ season, week, date, team: away, opp: home, home: 0, line: sp === null ? null : sp, margin: res === null ? null : -res, pf: r[8], pa: r[9] });
  }
  return out;
}
// Does a team cover when its line is shifted by `pts`? 1 = cover, 0 = push, -1 = no.
function teaseResult(margin, line, pts) {
  const x = margin + line + pts;
  return x > 0 ? 1 : x === 0 ? 0 : -1;
}
// Margins that the extra points newly cover, and which of them are key numbers.
function keysCrossed(line, pts) {
  const lo = -(line + pts), hi = -line, keys = new Set();
  for (let m = Math.floor(lo) + 1; m <= hi; m++) if (KEY_MARGINS.includes(Math.abs(m))) keys.add(Math.abs(m));
  return [...keys].sort((a, b) => a - b);
}
// How often teams with this line covered the teased line. Starts with the exact line and widens until there are enough games.
function legStats(TG, line, pts, minN) {
  const done = TG.filter((g) => g.line !== null && g.margin !== null);
  for (const w of [0, 0.5, 1, 1.5, 2]) {
    const s = done.filter((g) => Math.abs(g.line - line) <= w + 1e-9);
    if (s.length >= (minN || 80) || w === 2) {
      let c = 0, p = 0;
      for (const g of s) { const r = teaseResult(g.margin, g.line, pts); if (r === 1) c++; else if (r === 0) p++; }
      return { n: s.length, cover: s.length ? c / s.length : null, push: s.length ? p / s.length : null, width: w };
    }
  }
}
// A team's last N finished games, using the line each game had.
function teamRecent(TG, team, pts, n) {
  const s = TG.filter((g) => g.team === team && g.line !== null && g.margin !== null).slice(-n);
  let c = 0, p = 0;
  for (const g of s) { const r = teaseResult(g.margin, g.line, pts); if (r === 1) c++; else if (r === 0) p++; }
  return { n: s.length, cover: c, push: p };
}
// American odds -> profit per 1 staked, and the per-leg win rate needed to break even.
function oddsProfit(o) { return o > 0 ? o / 100 : 100 / Math.abs(o); }
function teaserBreakEven(odds, legs) { return legs > 0 ? Math.pow(1 / (1 + oddsProfit(odds)), 1 / legs) : null; }

// ---- Saved props / parlay math ----
// Accepts "-115", "−115", "+120", "120"; returns an integer American price or null.
function parseAmerican(v) {
  if (v === null || v === undefined) return null;
  const n = parseInt(String(v).replace(/[−–—]/g, "-").replace(/[^0-9+-]/g, ""), 10);
  return Number.isFinite(n) && Math.abs(n) >= 100 ? n : null;
}
const americanToDecimal = (o) => (o > 0 ? 1 + o / 100 : 1 + 100 / Math.abs(o));
function decimalToAmerican(d) {
  if (!(d > 1)) return null;
  return d >= 2 ? Math.round((d - 1) * 100) : -Math.round(100 / (d - 1));
}
// legs: [{odds: American|null, p: hit rate 0-1|null}]. Legs without odds are skipped and counted.
function parlayCombine(legs, stake) {
  const priced = legs.filter((l) => l.odds !== null && l.odds !== undefined);
  const dec = priced.reduce((a, l) => a * americanToDecimal(l.odds), 1);
  const ps = legs.filter((l) => l.p !== null && l.p !== undefined);
  return {
    n: legs.length, priced: priced.length, dec: priced.length ? dec : null,
    american: priced.length ? decimalToAmerican(dec) : null,
    implied: priced.length ? 1 / dec : null,
    payout: priced.length ? stake * dec : null, profit: priced.length ? stake * (dec - 1) : null,
    hist: ps.length === legs.length && legs.length ? ps.reduce((a, l) => a * l.p, 1) : null,
  };
}

if (typeof module !== "undefined") module.exports = { STATS, POS_STATS, getSample, median, summarize, defaultLine, leagueLine, DEF_TOP, defFamily, defSample, byDefense, roleTop, breakEven, matchupEstimate, rankEntries, parseLines, TEAM_NAMES, parseCSV, parseDK, matchPool, optimizeLineup, dkNorm, dkTeam, TEAM_COLORS, teamPill, teamGames, teaseResult, keysCrossed, legStats, teamRecent, oddsProfit, teaserBreakEven, KEY_MARGINS, parseAmerican, americanToDecimal, decimalToAmerican, parlayCombine };
