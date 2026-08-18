// Node-side half of tests/test_js_parity.py.
// Usage: node js_parity_runner.js <app_scoring.js> <dataset.json> <cases.json>
"use strict";
const fs = require("fs");
const CompEngine = require(process.argv[2]);
const dataset = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));

// mirrors SWAP_EVERY / SWAP_MAX_PARTY in test_js_parity.py
const SWAP_EVERY = 6, SWAP_MAX_PARTY = 6;
// mirrors REFINE_* in test_js_parity.py
const REFINE_EVERY = 6, REFINE_MAX_PARTY = 6, REFINE_PASSES = 2;

const out = cases.map((c, i) => {
  const e = new CompEngine(dataset, c.content, c.size, c.style);
  const sp = i % SWAP_EVERY === 0 ? c.party.slice(0, SWAP_MAX_PARTY) : null;
  const rp = i % REFINE_EVERY === 0 ? c.party.slice(0, REFINE_MAX_PARTY) : null;
  return {
    refine: rp === null ? null : e.refine(rp, REFINE_PASSES, c.refine_pool),
    comp_score: e.compScore(c.party),
    swap: sp === null ? null : e.swapReview(sp).map((m) => ({
      weapon: m.weapon, score: m.score, rank: m.rank,
      options: m.options.map((o) => ({ weapon: o.weapon, score: o.score })),
    })),
    fitness: e.fitness(c.party),
    synergy: e.synergy(c.party),
    max_fitness: e.maxFitness(),
    recommend: e.recommend(c.party, 5).map((r) => ({ weapon: r.weapon, score: r.score })),
    weaknesses: e.weaknesses(c.party, 5).map((g) => ({ cap: g.cap, gap: g.gap })),
    uncovered: e.uncoveredCaps(c.party).slice().sort(),
  };
});
process.stdout.write(JSON.stringify(out));
