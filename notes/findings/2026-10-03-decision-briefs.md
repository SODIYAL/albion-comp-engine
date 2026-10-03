# Decision briefs — 2026-10-03

Five open items measured on the roster artifact re-derived from the cache
on 2026-10-03 (window to 06:34 UTC; 276,782 battles, 350,606 parties) and
the committed dataset. Report only: nothing here changed a template, a
sheet or a weight. Each brief states what was measured, the options and
what each would touch. Every one needs a maintainer decision.

## 1. The roster artifact reaches GitHub's file limit in about two weeks

**Context.** `pipeline/out/party_rosters.json.gz` is 27 MB as committed
(the 2026-09-29 fold) and 49 MB re-derived today. The kill-feed poll
joined the artifact on 2026-09-27 and adds about 40,000 battles a day
(247,107 poll battles in six days against 29,265 battle-list battles in
five weeks). Uncompressed, `builds` is 595 MB of the artifact's 795 MB
(1,425,657 build records); `battles` 108 MB, `parties` 90 MB.

**Evidence.** Growth since the poll joined: about 22 MB in six days, 3.7
MB a day. At that rate the file passes 50 MB (GitHub's warning) at the
next fold and 100 MB (the hard limit: the push is refused) around
2026-10-17. The repository pack is 205 MiB with ten versions of the
artifact in history; each fold adds the whole new blob.

**Options.**

- Commit the populations the tables read, not the whole cache. Every
  shipped table reads `source="battle_list"` or `content="ancient_lands"`
  (`rosters_io.load`); the open-world poll records (260,627 of 350,606
  parties, tagged `open_world`) feed no table and no page. An artifact of
  the battle-list population plus the Ancient Lands records is the
  evidence the build uses; the rest stays in the cache, the way the raw
  cache already does. Touches `sample_parties.py analyze` (what it
  writes), `rosters_io`, the provenance hash, one fold to re-derive.
- Split by population into two files, each under the limit for longer.
  Defers the limit, does not remove the growth.
- Git LFS for the artifact. CI and a fresh clone need LFS; the pack stops
  growing.
- Commit aggregates only (the BACKLOG's earlier proposal). The builds are
  the evidence the kit doctrine votes on; the derived tables would lose
  their committed source.

The first option keeps "the committed artifact is the evidence the build
reads" true and removes four fifths of the bytes; it is the smallest
change that survives the growth. It needs deciding before the fold after
next.

## 2. The frontline the portal's fives field against the frontline the engine names

**Context.** The BACKLOG's "popularity baseline on the portal pools" item,
measured on the frontline seat of the 4-5 pool, where the gap is widest.
2,616 full parties of 4-5 (2,339 dominant).

**Evidence.** Share of dominant parties fielding each frontline weapon:
Heavy Mace 17.5% (410), Polehammer 12.4% (291), Mace 6.8% (160), Great
Hammer 6.7% (157), Oathkeepers 4.3%, Primal Staff 4.1%.

Leave-the-frontline-out on 150 dominant fives with exactly one frontline
(the committed engine, `ancient_lands` at 5, ranks among frontline
candidates): the engine's first frontline is Great Hammer in 103 cases,
Polehammer in 43, Oathkeepers in 4, Heavy Mace in none. Median frontline
rank: Great Hammer 1, Polehammer 2, Heavy Mace 4, Mace 4. The frontline
the winners fielded is first in 17 of 150, in the top three in 68, and
outside the suggestion pool in 26.

Heavy Mace against Great Hammer on the same 150 cores (`pick_report`):
mean score 9.31 against 13.88. By capability term (mean coverage delta,
Great Hammer minus Heavy Mace): stun +3.80, catch +1.86, heal_reduction
+1.47, resist_shred +0.87, disengage +0.86, burst_aoe +0.78, mobility
+0.75; peel -1.59, purge -1.06, tankiness -0.92. The meta term favours
Heavy Mace by 0.03. Heavy Mace's sheet: peel 6, purge 6, silence 6,
tankiness 6, engage 4, zone_control 4, no stun, no catch. Silence carries
no row at 5 (the median winning five fields none; 19% field some), so
the sheet's third 6 buys nothing in this pool.

**Hypotheses (standing rule 1: gate findings are hypotheses, never
fixes).**

- The `none` rule drops a capability a fifth of winners field. A row
  whose median winner fields none is no demand; silence at 4-5 is fielded
  by 19% of dominant fives, almost exactly Heavy Mace's own share. The
  rule reads "most winners do without it"; the harvest also says "the
  most fielded frontline is the one that brings it". A minority-fielded
  capability could carry a small row (its p75 instead of its median, or a
  weight without a target) instead of none.
- The capability score pays breadth: Great Hammer supplies a first unit
  on fourteen rows, Heavy Mace depth on four. The BACKLOG records the
  same shape for Battle Bracers over the Rotcaller Staff at 6-7.
- The Heavy Mace sheet under-credits what the pick is fielded for. A
  sheet review against the stat chart (its E and the W the fives equip)
  is curation, and a change there needs its evidence spell.
- The meta prior is too small to matter here (0.03 of a 4.6 gap); the
  BACKLOG's `delta` measurements say raising it fails T49 and T16 before
  it closes a gap this size.

**What would settle it.** A blind validation round on the 4-5 pool (the BACKLOG
item: `validated_sizes` is empty for `ancient_lands`): forms where the
frontline is the open seat, graded before the engine's answer. If the
grades name Heavy Mace, the first two hypotheses are the levers, in that
order.

## 3. The 15-20 portal pool is four rosters short of rows of its own

**Context.** `derive_portal_rows.py` gives a pool rows of its own at 40
distinct dominant rosters on the training split. Report-only run on
today's artifact.

**Evidence.** 15-20: 101 killer parties, 36 distinct dominant rosters on
the training split (trio 1,704, five 1,386, seven 253). The pool gained
61 parties in four days; it crosses the floor within days and the next
fold will derive its rows unless the decision says otherwise.

Two facts bear on the decision. The pool's dominant share is 46.5%
(47 of 101 parties took no deaths), against 87% to 93% in the smaller
pools: at twenty a side the winner usually loses someone, so "dominant"
keeps under half the evidence and may select stomps over good comps.
And all 36 field a healer and a frontline, 86% a support: the roster
profile on the portal page (frontline 3-5, healer 3-4, support 2-4, dps
7-9) reads like the ZvZ rows' own shape.

**Options.**

- Its own pool rows at the floor (the standing rule for 2-3 and 6-7).
  Consistent; the rows rest on about 40 rosters selected by a filter that
  keeps under half the winners.
- The style x size rows at 10+ (today's reading). No new rows; the portal
  twenty is treated as a ZvZ twenty.
- Its own rows on a wider evidence unit for this pool: the killer party
  with K/D of 2 or more instead of no deaths. More rosters, a different
  unit from the other pools: a logged decision of its own.

## 4. The raw cache has one copy

**Context.** `pipeline/out/party_cache.sqlite` is 560 MB, gitignored,
and the only copy of 276,782 battles of evidence; the kill feed it was
polled from does not serve history, so a lost disk loses the portal
pools for good.

**Options.** A nightly upload after the harvest to a storage bucket (a
backup, never a build input: CI and provenance unchanged), or a copy to a
second local disk in the harvest task. Either needs a destination and
credentials the repository does not hold.

## 5. The holdout read against the popularity baseline, on today's artifact

**Context.** `tests/tier2_blindtest.py v4h --baseline` (report only, never
a gate) on the artifact re-derived today and the committed dataset: 150
killer parties of 10-20 from the holdout slice (4,372 eligible), three
drops each, 450 drops.

**Evidence.** Role-level: the engine names the dropped member's role on
62% to 65% of drops across the three dressing modes (103 to 108 of 166);
the role-need-then-popularity baseline on 54% (90 of 166). Weapon in the
top 3: the engine 9% to 10%, the baseline 18%. Rank of the dropped weapon:
median 31 to 32 against 23; top-10 23% to 24% against 30%; MRR 0.10 to
0.11 against 0.163. By style label (harvest gear, role level): clap_kite
74%, balanced 65%, clap 60%, brawl 56%, kite 40% (8 parties).

The picture the BACKLOG records stands: the capability model leads on
which role a comp is missing and trails popularity on which weapon fills
it. Brief 2 is the same gap seen on one seat of one pool. The decision
the BACKLOG carries (raise `delta`, soften the duplicate cost, or accept
that the engine optimises comps and not the published pick) is unchanged
by this read; the kite cell stays the weakest and the least sampled.
