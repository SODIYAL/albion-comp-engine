// Node-side half of tests/test_js_parity.py.
// Usage: node js_parity_runner.js <app_scoring.js> <dataset.json> <cases.json>
"use strict";
const fs = require("fs");
const CompEngine = require(process.argv[2]);
const dataset = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const cases = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));

const out = cases.map((c) => {
  const e = new CompEngine(dataset, c.content, c.size);
  return {
    fitness: e.fitness(c.party),
    synergy: e.synergy(c.party),
    max_fitness: e.maxFitness(),
    recommend: e.recommend(c.party, 5).map((r) => ({ weapon: r.weapon, score: r.score })),
    weaknesses: e.weaknesses(c.party, 5).map((g) => ({ cap: g.cap, gap: g.gap })),
    uncovered: e.uncoveredCaps(c.party).slice().sort(),
  };
});
process.stdout.write(JSON.stringify(out));
