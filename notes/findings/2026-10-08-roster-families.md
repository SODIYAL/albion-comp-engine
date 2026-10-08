# R4: whole-roster clustering on killer parties of 16-20

## Context

This is a report-only measurement for a display question (BACKLOG "Whole-roster clustering on killer
parties"). The observed families on the page are anchor pairs. Clustering was rejected on the partial
alliance baskets, and was untested on full rosters. A cluster would only ever be shown, never scored.

- **Artifact.** The committed killer-party artifact at origin/main 6590a51,
  `pipeline/out/party_rosters.json.gz`, sha256
  `829c8c293b0735393e66cad37602562a8d6e162c9bfc8ab77992b7c23270ba4b` (the hash
  `pipeline/out/party_styles.json` records). The style labels come from that `party_styles.json`
  (`comp_identity`, weapons only, keyed by battle and party index). The anchor-pair families come from
  the committed `pipeline/out/cohort_families.json`, `large` bucket: 9 families mined from 1,000 evenly
  sampled killer parties of 16+ in a 28-day window, every population.
- **Population.** The battle-list population, parties of 16-20 with every member's weapon known and in
  the catalogue: 11,968 rosters with battle starts from 2026-08-28 to 2026-10-04, on 35 distinct
  battle days. Sizes:
  16: 1,958, 17: 2,145, 18: 2,464, 19: 2,736, 20: 2,665. 136 distinct weapons. The training split
  (battle % 5 != 0) holds 9,598 rosters and fits the clusters. The holdout (battle % 5 == 0) holds
  2,370 and checks them.
- **Primary guild and alliance.** The guild (alliance) with most members in the party. Both are read
  from the harvest cache's party record after the analyzer's own member-overlap dedupe, re-run exactly
  on a read-only snapshot of the cache (last write
  2026-10-08T19:54:12Z). A cache party is matched to the artifact's party on size and sorted
  weapons, which holds for 31,755 of the 31,784 parties of 10+.

## Method

- **Representation and distance.** A roster is its weapon multiset (a count vector over the 136
  weapons). The distance is 1 - weighted Jaccard: the sum of the per-weapon minima over the sum of the
  maxima. The set variant uses the distinct weapons (binary Jaccard). Two 20-man rosters at distance
  0.50 share about 13 of 20 slots; at 0.33, about 16.
- **Clustering, with nothing forced.** Average-linkage hierarchical clustering (scipy) on the full
  9,598 x 9,598 training distance matrix, cut at distance t. A family is a cluster of at least 50
  rosters (0.5% of the training split). Every other roster stays unclustered. The cut is swept over
  t = 0.30 to 0.70.
- **Nulls.** Both nulls keep every roster's size and the weapon marginals. In the shuffle null every
  slot of every roster is pooled and dealt back at random, which destroys co-occurrence. In the seat
  null the deal happens within each primary seat (the dataset's `label.seat`: 13 seats, plus one
  group for the two weapons with none), so each roster keeps its seat composition (main healers,
  engage tanks, ranged AoE ...). A family the seat null also produces is role balance plus
  popularity, not a family. Each null (3 replicates) is clustered exactly as the data.
- **Is the structure real?** Four checks, each against the nulls:
  - random-pair Jaccard;
  - nearest-neighbour distance, both to any roster and to the nearest roster of another primary guild
    and another primary alliance, so that a squad repeating its roster cannot be its own neighbour;
  - the family count, coverage and family-member silhouette at each cut;
  - a forced partition (k-medoids with k-medoids++ seeding, 2 restarts, on a fixed 4,000-roster
    subsample), with its silhouette and the gap statistic (mean log null cost - log cost).
- **Stability.** Clusterboot: 20 subsamples of 80% without replacement, each re-clustered at the same
  cut with the floor scaled. Each family gets the mean Jaccard of its best-matching subsample family.
  A mean of 0.75 or more reads stable, 0.60 to 0.75 a pattern, 0.50 to 0.60 weak, and below 0.50
  dissolved. The adjusted
  Rand index is computed on each subsample, with unclustered rosters as singletons.
- **Holdout.** Each holdout roster is assigned to its nearest family medoid and kept when it falls
  inside the family's radius (the 90th percentile of the training members' distance to the medoid).
  The holdout's joined share is set against the training coverage and against the joined share of a
  seat-null holdout under the same rule. The holdout is also clustered on its own at the same cut (the
  floor scaled to 12) and its families are matched to the nearest training medoid. The joined share is
  also read by ISO week.
- **Guild repeats.** The same squad fields the same roster across many battles. A variant keeps one
  roster per primary guild per day (the first in battle order; 11,968 rosters become 4,052) and runs
  the sweep and the families again with the floor scaled to 20.
- **Against the anchor pairs.** Each roster gets its anchor-pair family: the first family, in mined
  order, whose anchor pair it fields. Each anchor family's medoid is taken over every training roster
  assigned to it. For each roster cluster the report gives the members' mean distance to their own
  cluster medoid and to their anchor family's medoid, and how far apart the medoids of clusters sharing
  one anchor family sit.

## The numbers

### Is there structure? The multiset sweep against the nulls

**Random pairs barely separate from the nulls.** Training rosters 9,598, holdout 2,370, 136 weapons,
family floor 50 rosters, 3 replicates of each null. The random-pair weighted Jaccard (median / p90)
reads:

| Rosters | Median | p90 |
| --- | ---: | ---: |
| observed | 0.20 | 0.37 |
| shuffle null | 0.17 | 0.27 |
| seat null | 0.19 | 0.29 |

The set variant reads 0.22 / 0.41, the figure the BACKLOG quotes, against nulls of 0.19-0.20 /
0.30-0.31. The structure lives in the near neighbours:

| Nearest-neighbour distance | q10 | Median | q90 | Share within 0.35 |
| --- | ---: | ---: | ---: | ---: |
| observed, any roster | 0.00 | 0.20 | 0.50 | 0.726 |
| observed, another primary guild and alliance | 0.20 | 0.40 | 0.57 | 0.377 |
| shuffle null, any roster | 0.46 | 0.52 | 0.58 | 0.001 |
| shuffle null, another primary guild and alliance | 0.46 | 0.52 | 0.58 | 0.001 |
| seat null, any roster | 0.43 | 0.50 | 0.58 | 0.005 |
| seat null, another primary guild and alliance | 0.43 | 0.50 | 0.58 | 0.005 |

- **Most near neighbours are the same squad.** A tenth of the rosters have an identical multiset
  elsewhere in the training split. 72% of nearest neighbours share the primary guild, and 66% the
  primary alliance.
- **Organizations still converge.** The nearest roster of another guild and another alliance sits at
  a median 0.40, against 0.50-0.52 in both nulls. 38% of rosters have such a neighbour within 0.35
  (about 16 of 20 slots shared), against 0.1-0.5% under the nulls.
- **The seat null explains almost none of it.** Role balance plus weapon popularity produces near
  neighbours at nearly the shuffle-null rate.

Average linkage, cut at t (families: clusters of 50+ rosters):

| Cut t | Families | Coverage | Family silhouette | Shuffle null: families / coverage | Seat null: families / coverage |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 0.30 | 3 | 0.026 | 0.345 | 0.0 / 0.000 | 0.0 / 0.000 |
| 0.35 | 5 | 0.052 | 0.284 | 0.0 / 0.000 | 0.0 / 0.000 |
| 0.40 | 10 | 0.101 | 0.271 | 0.0 / 0.000 | 0.0 / 0.000 |
| 0.45 | 12 | 0.164 | 0.204 | 0.0 / 0.000 | 0.0 / 0.000 |
| 0.50 | 14 | 0.223 | 0.185 | 0.0 / 0.000 | 0.0 / 0.000 |
| 0.55 | 15 | 0.304 | 0.138 | 0.0 / 0.000 | 0.0 / 0.000 |
| 0.60 | 18 | 0.449 | 0.116 | 0.0 / 0.000 | 0.0 / 0.000 |
| 0.65 | 17 | 0.570 | 0.103 | 0.0 / 0.000 | 0.0 / 0.000 |
| 0.70 | 11 | 0.681 | 0.099 | 0.7 / 0.004 | 5.0 / 0.036 |

A forced partition (k-medoids on a fixed 4,000-roster subsample):

| k | Silhouette | Shuffle null | Seat null | Gap vs shuffle | Gap vs seat |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 0.082 | 0.014 | 0.015 | 0.159 | 0.125 |
| 3 | 0.080 | 0.012 | 0.012 | 0.163 | 0.132 |
| 4 | 0.067 | 0.010 | 0.011 | 0.172 | 0.143 |
| 6 | 0.070 | 0.009 | 0.011 | 0.193 | 0.169 |
| 8 | 0.038 | 0.007 | 0.009 | 0.215 | 0.157 |
| 12 | 0.036 | 0.008 | 0.008 | 0.200 | 0.190 |

- **The structure is local, not a partition.** Below t = 0.70 the nulls form no family at all, while
  the data form 3 to 18. Every family at those cuts is beyond what sizes, popularity and role balance
  produce.
- **Separation is weak where coverage is useful.** Family silhouettes run 0.27-0.35 at t <= 0.40
  (10% or less of the rosters) and 0.12-0.19 at t = 0.50-0.60 (22-45%).
- **Forcing every roster into k groups finds almost nothing.** Silhouette 0.04-0.08 at any k. The gap
  over both nulls is positive but flat in k: the density is concentrated, without a natural number of
  families.
- **The rosters are a continuum with dense pockets.** The pockets are what a family display could
  show.
- **The set variant agrees**: families form at every cut up to 0.60
  with no null family, coverage 0.14 / 0.31 / 0.51 at t 0.40 / 0.50 / 0.60, family silhouette 0.24 /
  0.14 / 0.12, k-medoids silhouette 0.04-0.11.

### The families at t = 0.50 (multiset, every training roster)

**The run.** 14 families of 50+ rosters cover 22.3% of the 9,598 training rosters; family silhouette
0.186; clusterboot adjusted Rand index 0.73 on average (minimum 0.66) over 20 subsamples of 80%.

**The holdout.**

- 30.0% of the 2,370 holdout rosters fall inside a family radius, against 0.3% of seat-null holdout
  rosters. Per family, the holdout share tracks the training share.
- Clustered on its own at the same cut, the holdout forms 19 families.
- The joined share is flat across the window: 0.29 to 0.31 in every ISO week from 36 to 40 (0.39 in
  week 35, 54 rosters).

**Reading the table.**

- Read: stability (clusterboot mean Jaccard) and who fields the family. "One guild" means one
  primary guild holds half the rosters or more; "one alliance" the same for an alliance; "multi-org"
  otherwise.
- The last column is each family's anchor-pair family: the first committed family, in mined order,
  whose anchor pair the roster fields. 0 is Realmbreaker + Spiked Gauntlets and 3 is Galatine Pair +
  Dreadstorm Monarch (the list is under "Against the anchor pairs").
- Styles count `party_styles.json` labels, top three shown.

| Family | Rosters | Battles | Days | Primary guilds | Top guild | Top alliance | Orgs | Styles | Mean Jaccard (dissolved share) | Read | Holdout share (training share) | Holdout clusters matched (medoid distance) | Distance to own / anchor-family medoid | Anchor family (share) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | --- | ---: | --- |
| 0 | 924 | 817 | 33 | 85 | 0.07 | 0.114 | 27 | clap_kite 552, clap 187, kite 184 | 0.75 (0.00) | stable, multi-org | 0.111 (0.096) | 0.19, 0.38 | 0.32 / 0.33 | 0 Realmbreaker + Spiked Gauntlets (0.94) |
| 1 | 146 | 146 | 30 | 9 | 0.65 | 0.657 | 8 | clap 136, unlabelled 10 | 0.69 (0.00) | pattern, one guild | 0.016 (0.015) | 0.18 | 0.32 / 0.63 | 0 Realmbreaker + Spiked Gauntlets (0.96) |
| 2 | 135 | 132 | 27 | 10 | 0.82 | 0.836 | 9 | clap_kite 112, clap 12, kite 11 | 0.71 (0.15) | pattern, one guild | 0.012 (0.014) | none | 0.27 / 0.44 | 0 Realmbreaker + Spiked Gauntlets (0.94) |
| 3 | 130 | 130 | 31 | 37 | 0.18 | 0.212 | 19 | clap 81, clap_kite 47, kite 2 | 0.39 (0.75) | dissolves, multi-org | 0.059 (0.013) | 0.32, 0.33, 0.25, 0.27, 0.46, 0.30 | 0.35 / 0.48 | 0 Realmbreaker + Spiked Gauntlets (0.85) |
| 4 | 104 | 103 | 27 | 17 | 0.55 | 0.475 | 15 | clap_kite 80, clap 17, kite 7 | 0.74 (0.00) | pattern, one guild | 0.012 (0.011) | 0.10 | 0.29 / 0.49 | 0 Realmbreaker + Spiked Gauntlets (0.90) |
| 5 | 102 | 102 | 23 | 9 | 0.45 | 0.451 | 7 | clap 102 | 0.90 (0.00) | stable, multi-org | 0.010 (0.011) | 0.15 | 0.31 / 0.74 | 0 Realmbreaker + Spiked Gauntlets (0.93) |
| 6 | 100 | 99 | 27 | 10 | 0.58 | 0.576 | 9 | brawl 67, unlabelled 25, clap 7 | 0.84 (0.00) | stable, one guild | 0.007 (0.010) | none | 0.25 / 0.75 | 0 Realmbreaker + Spiked Gauntlets (0.82) |
| 7 | 96 | 95 | 25 | 8 | 0.47 | 0.469 | 8 | clap 96 | 0.85 (0.00) | stable, multi-org | 0.019 (0.010) | 0.05, 0.46 | 0.29 / 0.67 | 0 Realmbreaker + Spiked Gauntlets (0.93) |
| 8 | 89 | 89 | 23 | 7 | 0.89 | 0.59 | 7 | clap 43, unlabelled 31, brawl 15 | 0.83 (0.00) | stable, one guild | 0.013 (0.009) | 0.14, 0.67 | 0.29 / 0.77 | 0 Realmbreaker + Spiked Gauntlets (0.87) |
| 9 | 77 | 76 | 22 | 7 | 0.79 | 0.818 | 6 | clap_kite 37, kite 27, clap 13 | 0.79 (0.10) | stable, one guild | 0.012 (0.008) | 0.00 | 0.21 / 0.52 | 0 Realmbreaker + Spiked Gauntlets (0.86) |
| 10 | 76 | 76 | 29 | 4 | 0.96 | 0.921 | 4 | clap 71, unlabelled 3, brawl 2 | 0.80 (0.00) | stable, one guild | 0.010 (0.008) | 0.18 | 0.36 / 0.72 | 0 Realmbreaker + Spiked Gauntlets (0.88) |
| 11 | 59 | 59 | 17 | 19 | 0.39 | 0.186 | 16 | clap_kite 37, clap 16, kite 6 | 0.27 (0.65) | dissolves, multi-org | 0.007 (0.006) | 0.20 | 0.34 / 0.45 | 0 Realmbreaker + Spiked Gauntlets (0.90) |
| 12 | 52 | 51 | 11 | 1 | 1.00 | 0.923 | 1 | clap 34, unlabelled 8, kite 6 | 0.80 (0.15) | stable, one guild | 0.005 (0.005) | none | 0.34 / 0.68 | 0 Realmbreaker + Spiked Gauntlets (0.88) |
| 13 | 51 | 51 | 17 | 1 | 1.00 | 1.0 | 1 | brawl 41, unlabelled 10 | 0.64 (0.30) | pattern, one guild | 0.006 (0.005) | 0.27 | 0.32 / 0.59 | 3 Galatine Pair + Dreadstorm Monarch (0.76) |

**Medoid rosters.** These are the members' most-central rosters; "most fielded" gives a weapon's share
of the family's rosters and its mean copies where fielded.

| Family | Medoid roster | Most fielded (share, mean copies when fielded) |
| ---: | --- | --- |
| 0 | 19: 3 x Hallowfall, 2 x Bedrock Mace, Arcane Staff, Dawnsong, Exalted Staff, Great Arcane Staff, Hand of Justice, Oathkeepers, Occult Staff, Permafrost Prism, Polehammer, Realmbreaker, Rotcaller Staff, Spiked Gauntlets, Spirithunter, Witchwork Staff | Permafrost Prism 0.99 (x1.3), Hallowfall 0.99 (x2.2), Bedrock Mace 0.99 (x1.8), Spiked Gauntlets 0.97 (x1.0), Realmbreaker 0.96 (x1.0), Spirithunter 0.94 (x1.0), Occult Staff 0.93 (x1.1), Witchwork Staff 0.89 (x1.0), Great Arcane Staff 0.86 (x1.1), Rotcaller Staff 0.77 (x1.0) |
| 1 | 20: 2 x Hallowfall, 2 x Longbow, Arcane Staff, Battle Bracers, Exalted Staff, Great Arcane Staff, Great Frost Staff, Mace, Malevolent Locus, Nature Staff, Oathkeepers, Permafrost Prism, Polehammer, Realmbreaker, Rootbound Staff, Shadowcaller, Spiked Gauntlets, Spirithunter | Hallowfall 1.00 (x2.1), Realmbreaker 0.99 (x1.5), Oathkeepers 0.99 (x1.2), Spiked Gauntlets 0.97 (x1.0), Malevolent Locus 0.95 (x1.0), Mace 0.94 (x1.3), Polehammer 0.89 (x1.0), Spirithunter 0.81 (x1.0), Great Arcane Staff 0.81 (x1.0), Longbow 0.81 (x1.7) |
| 2 | 19: 2 x Bedrock Mace, Arcane Staff, Damnation Staff, Dawnsong, Earthrune Staff, Exalted Staff, Forgebark Staff, Hallowfall, Hoarfrost Staff, Longbow, Oathkeepers, Occult Staff, Permafrost Prism, Realmbreaker, Rotcaller Staff, Spiked Gauntlets, Spirithunter, Witchwork Staff | Spiked Gauntlets 0.98 (x1.0), Permafrost Prism 0.98 (x1.3), Occult Staff 0.96 (x1.1), Bedrock Mace 0.96 (x1.8), Realmbreaker 0.96 (x1.0), Hallowfall 0.95 (x1.3), Witchwork Staff 0.93 (x1.1), Rotcaller Staff 0.87 (x1.0), Exalted Staff 0.87 (x1.0), Spirithunter 0.87 (x1.0) |
| 3 | 18: 2 x Hallowfall, Bedrock Mace, Dawnsong, Earthrune Staff, Fallen Staff, Great Arcane Staff, Lifecurse Staff, Oathkeepers, Occult Staff, Permafrost Prism, Polehammer, Realmbreaker, Rift Glaive, Rootbound Staff, Spiked Gauntlets, Spirithunter, Witchwork Staff | Hallowfall 0.99 (x2.1), Permafrost Prism 0.97 (x1.0), Bedrock Mace 0.96 (x1.4), Earthrune Staff 0.95 (x1.0), Spiked Gauntlets 0.93 (x1.0), Realmbreaker 0.91 (x1.0), Spirithunter 0.90 (x1.0), Dawnsong 0.86 (x1.1), Lifecurse Staff 0.84 (x1.0), Oathkeepers 0.82 (x1.1) |
| 4 | 20: 3 x Hallowfall, 2 x Bedrock Mace, 2 x Rift Glaive, Dawnsong, Demonic Staff, Great Arcane Staff, Hand of Justice, Incubus Mace, Oathkeepers, Occult Staff, Permafrost Prism, Polehammer, Rampant Staff, Realmbreaker, Spiked Gauntlets, Spirithunter | Hallowfall 1.00 (x2.9), Permafrost Prism 0.98 (x1.0), Rift Glaive 0.95 (x1.8), Realmbreaker 0.95 (x1.0), Spiked Gauntlets 0.95 (x1.0), Bedrock Mace 0.95 (x1.5), Spirithunter 0.92 (x1.0), Oathkeepers 0.91 (x1.0), Hand of Justice 0.89 (x1.0), Occult Staff 0.88 (x1.1) |
| 5 | 18: 4 x Longbow, 3 x Hallowfall, 2 x Mace, Carving Sword, Great Arcane Staff, Hammer, Heavy Mace, Nature Staff, Oathkeepers, Realmbreaker, Shadowcaller, Spiked Gauntlets | Hallowfall 1.00 (x2.6), Longbow 1.00 (x3.2), Spiked Gauntlets 0.99 (x1.0), Shadowcaller 0.98 (x1.0), Mace 0.98 (x1.8), Carving Sword 0.95 (x1.0), Realmbreaker 0.94 (x1.0), Nature Staff 0.86 (x1.0), Oathkeepers 0.78 (x1.2), Heavy Mace 0.69 (x1.2) |
| 6 | 19: 4 x Battle Bracers, 3 x Hallowfall, Carving Sword, Exalted Staff, Hammer, Heavy Mace, Incubus Mace, Lifecurse Staff, Mace, Malevolent Locus, Realmbreaker, Shadowcaller, Spiked Gauntlets, Spirithunter | Hallowfall 1.00 (x2.7), Battle Bracers 1.00 (x3.5), Mace 0.97 (x1.1), Shadowcaller 0.93 (x1.0), Realmbreaker 0.92 (x1.0), Spirithunter 0.92 (x1.0), Spiked Gauntlets 0.90 (x1.0), Lifecurse Staff 0.84 (x1.0), Exalted Staff 0.82 (x1.0), Hammer 0.81 (x1.0) |
| 7 | 20: 2 x Hallowfall, 2 x Longbow, Earthrune Staff, Exalted Staff, Great Arcane Staff, Great Frost Staff, Heavy Mace, Incubus Mace, Lifecurse Staff, Malevolent Locus, Nature Staff, Oathkeepers, Permafrost Prism, Polehammer, Realmbreaker, Shadowcaller, Spiked Gauntlets, Spirithunter | Hallowfall 1.00 (x2.1), Spiked Gauntlets 0.99 (x1.0), Longbow 0.98 (x1.9), Spirithunter 0.96 (x1.0), Earthrune Staff 0.94 (x1.0), Realmbreaker 0.94 (x1.0), Incubus Mace 0.93 (x1.0), Heavy Mace 0.85 (x1.0), Nature Staff 0.83 (x1.0), Malevolent Locus 0.81 (x1.0) |
| 8 | 20: 2 x Battle Bracers, 2 x Hallowfall, 2 x Longbow, Blight Staff, Carving Sword, Fallen Staff, Great Arcane Staff, Hammer, Heavy Mace, Mace, Malevolent Locus, Oathkeepers, Realmbreaker, Rootbound Staff, Rotcaller Staff, Shadowcaller, Spiked Gauntlets | Hallowfall 1.00 (x1.8), Battle Bracers 1.00 (x2.2), Mace 0.97 (x1.1), Spiked Gauntlets 0.94 (x1.0), Shadowcaller 0.94 (x1.0), Blight Staff 0.94 (x1.0), Realmbreaker 0.92 (x1.0), Rootbound Staff 0.91 (x1.0), Carving Sword 0.90 (x1.0), Longbow 0.81 (x1.4) |
| 9 | 20: 2 x Arcane Staff, 2 x Bedrock Mace, Bloodletter, Damnation Staff, Dawnsong, Earthrune Staff, Energy Shaper, Exalted Staff, Great Frost Staff, Hallowfall, Incubus Mace, Occult Staff, Permafrost Prism, Rampant Staff, Realmbreaker, Spiked Gauntlets, Spirithunter, Witchwork Staff | Witchwork Staff 1.00 (x1.0), Hallowfall 1.00 (x1.2), Earthrune Staff 1.00 (x1.0), Spirithunter 0.99 (x1.0), Bedrock Mace 0.99 (x1.8), Arcane Staff 0.97 (x2.0), Permafrost Prism 0.97 (x1.4), Occult Staff 0.96 (x1.0), Spiked Gauntlets 0.95 (x1.0), Dawnsong 0.94 (x1.0) |
| 10 | 20: 3 x Great Frost Staff, 3 x Hallowfall, Arcane Staff, Blight Staff, Bloodletter, Damnation Staff, Dawnsong, Hammer, Heavy Mace, Lifecurse Staff, Mace, Malevolent Locus, Oathkeepers, Realmbreaker, Spiked Gauntlets, Spirithunter | Hallowfall 1.00 (x2.7), Lifecurse Staff 0.99 (x1.0), Mace 0.99 (x1.1), Spiked Gauntlets 0.95 (x1.0), Realmbreaker 0.93 (x1.3), Great Frost Staff 0.93 (x2.4), Malevolent Locus 0.92 (x1.0), Spirithunter 0.91 (x1.0), Oathkeepers 0.88 (x1.0), Blight Staff 0.84 (x1.0) |
| 11 | 18: 2 x Hallowfall, 2 x Longbow, Bedrock Mace, Dawnsong, Forgebark Staff, Great Arcane Staff, Hand of Justice, Icicle Staff, Oathkeepers, Occult Staff, Permafrost Prism, Realmbreaker, Rotcaller Staff, Spiked Gauntlets, Spirithunter, Witchwork Staff | Hallowfall 1.00 (x2.6), Permafrost Prism 0.98 (x1.1), Bedrock Mace 0.98 (x1.3), Realmbreaker 0.97 (x1.0), Witchwork Staff 0.93 (x1.0), Spiked Gauntlets 0.93 (x1.0), Spirithunter 0.92 (x1.0), Longbow 0.90 (x1.4), Occult Staff 0.88 (x1.1), Hand of Justice 0.88 (x1.0) |
| 12 | 20: 2 x Realmbreaker, Battle Bracers, Blazing Staff, Carving Sword, Earthrune Staff, Energy Shaper, Exalted Staff, Fallen Staff, Hallowfall, Icicle Staff, Incubus Mace, Malevolent Locus, Oathkeepers, Permafrost Prism, Polehammer, Shadowcaller, Spiked Gauntlets, Spirithunter, Wild Staff | Permafrost Prism 1.00 (x1.0), Spiked Gauntlets 1.00 (x1.0), Earthrune Staff 1.00 (x1.0), Carving Sword 0.96 (x1.0), Shadowcaller 0.96 (x1.0), Malevolent Locus 0.94 (x1.0), Oathkeepers 0.92 (x1.2), Spirithunter 0.90 (x1.0), Hallowfall 0.90 (x1.7), Realmbreaker 0.89 (x1.2) |
| 13 | 18: 2 x Demonfang, 2 x Galatine Pair, 2 x Hallowfall, Arcane Staff, Bloodletter, Camlann Mace, Damnation Staff, Dreadstorm Monarch, Great Arcane Staff, Mace, Nature Staff, Redemption Staff, Shadowcaller, Staff of Balance, Ursine Maulers | Mace 1.00 (x1.1), Bloodletter 1.00 (x1.2), Hallowfall 0.98 (x1.9), Great Arcane Staff 0.96 (x1.0), Nature Staff 0.94 (x1.0), Dreadstorm Monarch 0.94 (x1.0), Demonfang 0.92 (x2.5), Galatine Pair 0.90 (x2.4), Damnation Staff 0.88 (x1.0), Arcane Staff 0.84 (x1.1) |

Training rosters per family by ISO week of the battle start:

| Family | w35 | w36 | w37 | w38 | w39 | w40 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 34 | 82 | 203 | 193 | 199 | 213 |
| 1 | 7 | 10 | 44 | 33 | 38 | 14 |
| 2 | 1 | 3 | 22 | 37 | 31 | 41 |
| 3 | 1 | 10 | 33 | 20 | 36 | 30 |
| 4 | 1 | 6 | 32 | 19 | 15 | 31 |
| 5 | 0 | 4 | 12 | 13 | 12 | 61 |
| 6 | 8 | 15 | 23 | 13 | 14 | 27 |
| 7 | 0 | 2 | 10 | 15 | 34 | 35 |
| 8 | 2 | 6 | 27 | 30 | 14 | 10 |
| 9 | 0 | 3 | 6 | 22 | 19 | 27 |
| 10 | 2 | 8 | 18 | 13 | 22 | 13 |
| 11 | 0 | 8 | 10 | 6 | 18 | 17 |
| 12 | 2 | 0 | 38 | 12 | 0 | 0 |
| 13 | 5 | 6 | 15 | 20 | 5 | 0 |

**What holds, by family.**

- **Family 0 is the one broad family.**
  - It holds 924 rosters (9.6% of the training split) across 817 battles, on 33 of the population's
    35 battle days (2026-08-28 to 2026-10-04), and it is present in every ISO week (34 to 213
    rosters a week).
  - It spans 85 primary guilds, none above 7% (the top three 18.5%), 55 primary alliances (the top
    one 11.4%) and 27 organizations.
  - It is stable (mean Jaccard 0.75, never dissolved).
  - It recurs on the holdout at its training rate (11.1% against 9.6%), and two holdout families sit
    at medoid distances 0.19 and 0.38 from it.
  - Styles: clap_kite 552, clap 187, kite 184.
  - Its medoid is the meta lineup: 3 x Hallowfall, 2 x Bedrock Mace, Realmbreaker, Spiked Gauntlets,
    Spirithunter, Permafrost Prism, Occult Staff, Witchwork Staff, Great Arcane Staff, Rotcaller
    Staff, Oathkeepers, Polehammer, Dawnsong, Exalted Staff, Arcane Staff and Hand of Justice.
- **Nine families are one guild's lineup** (1, 2, 4, 6, 8, 9, 10, 12, 13: one guild holds 55% to
  100%). They read stable or pattern because a squad repeating its roster reproduces under any
  resample. Families 12 and 13 are a single guild each, and family 12 exists only from 2026-08-28 to
  2026-09-16.
- **Two few-guild families.** Families 5 and 7 are stable lineups of 8 and 9 guilds in which one guild
  holds 45% and 47%: a Longbow-heavy clap lineup (4 x Longbow, 3 x Hallowfall, 2 x Mace, Shadowcaller,
  Carving Sword) and a Longbow / Earthrune / Incubus clap lineup. Both exist only from 2026-09-05.
- **The two broad multi-org clusters besides family 0 dissolve.** Family 3 (37 guilds) has mean
  Jaccard 0.39 and family 11 (19 guilds) 0.27.

### The cut, the variant and the guild repeats

| Run | Training rosters | Families | Coverage | Family silhouette | Clusterboot ARI | Holdout inside a radius (seat null) | Meta family: rosters, primary guilds, top guild, mean Jaccard | The other families |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| multiset t 0.40 | 9,598 | 10 | 0.101 | 0.271 | 0.67 | 0.151 (0.000) | 375, 44, 0.17, 0.68 | 7 one guild; 2 multi-org, both dissolve |
| multiset t 0.50 | 9,598 | 14 | 0.223 | 0.186 | 0.73 | 0.300 (0.003) | 924, 85, 0.07, 0.75 | 9 one guild; 2 few-guild (top guild 0.45, 0.47); 2 multi-org dissolve |
| multiset t 0.60 | 9,598 | 18 | 0.449 | 0.116 | 0.77 | 0.579 (0.100) | 1,893, 152, 0.07, 0.81 | 7 one guild; 3 one alliance; 4 multi-org that hold (weak to stable, the top guild 0.31-0.43); 3 multi-org dissolve |
| set t 0.50 | 9,598 | 15 | 0.312 | 0.140 | 0.75 | 0.399 (0.021) | 1,335, 105, 0.09, 0.79 | 8 one guild; 1 one alliance; 2 few-guild stable (top guild 0.40, 0.47); 3 multi-org dissolve |
| multiset, one roster per guild per day, t 0.50 | 3,225 | 10 | 0.205 | 0.133 | 0.68 | 0.260 (0.006) | 406, 96, 0.05, 0.71 | 6 one guild; 2 small multi-org patterns (28 and 23 rosters, 16 and 11 guilds, top guild 0.29 and 0.30, mean Jaccard 0.65 and 0.63); 1 multi-org dissolves |

- **The meta family is in every run.** It is the largest family, inside anchor family 0, with no
  guild above 17%, mean Jaccard 0.68 to 0.81, and the same medoid core.
- **The looser cut makes little real gain.** At t = 0.60 the coverage doubles, but the gain is the
  meta family absorbing its neighbours (1,893 rosters) and multi-org clusters that dissolve (one of
  507 rosters at mean Jaccard 0.43). The seat-null holdout starts joining (10%).
- **Under the guild-day dedupe** a squad's repeat sightings count once a day. The nearest neighbour
  then shares the primary guild for 35% of rosters (72% before). The cross-organization neighbour
  stays at a median 0.41 against 0.54-0.56 in the nulls, with 34% within 0.35 against 0.0-0.2%. The
  nulls still form no family below t = 0.70.

The one-roster-per-guild-per-day families at t = 0.50:

| Family | Rosters | Battles | Days | Primary guilds | Top guild | Top alliance | Orgs | Styles | Mean Jaccard (dissolved share) | Read | Holdout share (training share) | Holdout clusters matched (medoid distance) | Distance to own / anchor-family medoid | Anchor family (share) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | ---: | --- | ---: | --- |
| 0 | 406 | 365 | 33 | 96 | 0.05 | 0.099 | 34 | clap_kite 229, clap 99, kite 78 | 0.71 (0.00) | pattern, multi-org | 0.114 (0.126) | 0.14, 0.38, 0.39, 0.44, 0.23, 0.81 | 0.33 / 0.40 | 0 Realmbreaker + Spiked Gauntlets (0.94) |
| 1 | 40 | 40 | 26 | 22 | 0.23 | 0.2 | 15 | clap_kite 22, clap 15, kite 3 | 0.29 (0.75) | dissolves, multi-org | 0.036 (0.012) | 0.44, 0.64, 0.57, 0.46 | 0.39 / 0.48 | 0 Realmbreaker + Spiked Gauntlets (0.93) |
| 2 | 34 | 34 | 22 | 7 | 0.50 | 0.441 | 6 | clap 34 | 0.81 (0.05) | stable, one guild | 0.004 (0.011) | 0.38, 0.46, 0.77 | 0.33 / 0.62 | 0 Realmbreaker + Spiked Gauntlets (0.97) |
| 3 | 32 | 32 | 23 | 10 | 0.59 | 0.469 | 9 | clap_kite 26, kite 4, clap 2 | 0.62 (0.15) | pattern, one guild | 0.017 (0.010) | 0.10 | 0.28 / 0.56 | 0 Realmbreaker + Spiked Gauntlets (0.84) |
| 4 | 28 | 28 | 18 | 16 | 0.29 | 0.308 | 7 | clap 20, clap_kite 6, kite 2 | 0.65 (0.05) | pattern, multi-org | 0.046 (0.009) | 0.38, 0.30, 0.46, 0.27, 0.36 | 0.29 / 0.46 | 0 Realmbreaker + Spiked Gauntlets (0.93) |
| 5 | 26 | 26 | 22 | 4 | 0.81 | 0.826 | 4 | clap_kite 21, kite 3, clap 2 | 0.55 (0.30) | weak, one guild | 0.007 (0.008) | none | 0.27 / 0.46 | 0 Realmbreaker + Spiked Gauntlets (0.96) |
| 6 | 25 | 25 | 19 | 8 | 0.60 | 0.455 | 8 | unlabelled 11, brawl 8, clap 6 | 0.77 (0.10) | stable, one guild | 0.007 (0.008) | 0.27 | 0.32 / 0.70 | 0 Realmbreaker + Spiked Gauntlets (0.84) |
| 7 | 24 | 24 | 18 | 10 | 0.54 | 0.348 | 9 | kite 11, clap_kite 10, clap 3 | 0.14 (0.90) | dissolves, one guild | 0.013 (0.007) | none | 0.33 / 0.50 | 0 Realmbreaker + Spiked Gauntlets (0.83) |
| 8 | 23 | 23 | 15 | 11 | 0.30 | 0.318 | 10 | brawl 14, unlabelled 4, clap 4 | 0.63 (0.25) | pattern, multi-org | 0.006 (0.007) | 0.46 | 0.30 / 0.77 | 0 Realmbreaker + Spiked Gauntlets (0.96) |
| 9 | 22 | 22 | 18 | 7 | 0.73 | 0.727 | 6 | kite 9, clap_kite 8, clap 5 | 0.72 (0.10) | pattern, one guild | 0.010 (0.007) | 0.10 | 0.25 / 0.56 | 0 Realmbreaker + Spiked Gauntlets (0.86) |

| Family | Medoid roster | Most fielded (share, mean copies when fielded) |
| ---: | --- | --- |
| 0 | 19: 3 x Hallowfall, 2 x Bedrock Mace, Arcane Staff, Dawnsong, Earthrune Staff, Exalted Staff, Great Arcane Staff, Oathkeepers, Occult Staff, Permafrost Prism, Polehammer, Realmbreaker, Rotcaller Staff, Spiked Gauntlets, Spirithunter, Witchwork Staff | Hallowfall 1.00 (x2.3), Permafrost Prism 0.99 (x1.3), Bedrock Mace 0.98 (x1.7), Spiked Gauntlets 0.97 (x1.0), Realmbreaker 0.97 (x1.0), Spirithunter 0.91 (x1.0), Occult Staff 0.90 (x1.1), Great Arcane Staff 0.86 (x1.1), Witchwork Staff 0.84 (x1.0), Oathkeepers 0.83 (x1.0) |
| 1 | 20: 2 x Bedrock Mace, 2 x Hallowfall, 2 x Rift Glaive, Blight Staff, Dawnsong, Earthrune Staff, Energy Shaper, Great Arcane Staff, Heavy Mace, Lifecurse Staff, Oathkeepers, Permafrost Prism, Realmbreaker, Redemption Staff, Rootbound Staff, Spiked Gauntlets, Spirithunter | Spirithunter 1.00 (x1.0), Realmbreaker 0.97 (x1.0), Bedrock Mace 0.97 (x1.6), Permafrost Prism 0.95 (x1.0), Earthrune Staff 0.95 (x1.0), Hallowfall 0.95 (x1.6), Spiked Gauntlets 0.95 (x1.0), Blight Staff 0.90 (x1.2), Lifecurse Staff 0.85 (x1.0), Rift Glaive 0.85 (x1.4) |
| 2 | 20: 2 x Hallowfall, 2 x Longbow, 2 x Mace, 2 x Realmbreaker, Arcane Staff, Exalted Staff, Great Arcane Staff, Incubus Mace, Malevolent Locus, Nature Staff, Oathkeepers, Permafrost Prism, Polehammer, Shadowcaller, Spiked Gauntlets, Spirithunter | Oathkeepers 1.00 (x1.4), Spiked Gauntlets 1.00 (x1.0), Hallowfall 1.00 (x2.2), Realmbreaker 0.97 (x1.5), Permafrost Prism 0.97 (x1.0), Longbow 0.94 (x1.8), Spirithunter 0.94 (x1.0), Shadowcaller 0.91 (x1.0), Malevolent Locus 0.88 (x1.0), Polehammer 0.85 (x1.0) |
| 3 | 20: 3 x Hallowfall, 2 x Bedrock Mace, 2 x Rift Glaive, Dawnsong, Demonic Staff, Great Arcane Staff, Hand of Justice, Hoarfrost Staff, Incubus Mace, Oathkeepers, Occult Staff, Permafrost Prism, Rampant Staff, Realmbreaker, Spiked Gauntlets, Spirithunter | Permafrost Prism 1.00 (x1.0), Rift Glaive 1.00 (x1.9), Hallowfall 1.00 (x2.9), Spiked Gauntlets 0.97 (x1.0), Bedrock Mace 0.97 (x1.6), Occult Staff 0.94 (x1.0), Spirithunter 0.91 (x1.0), Hand of Justice 0.91 (x1.0), Realmbreaker 0.88 (x1.1), Oathkeepers 0.84 (x1.1) |
| 4 | 18: 2 x Hallowfall, Bedrock Mace, Dawnsong, Earthrune Staff, Fallen Staff, Great Arcane Staff, Lifecurse Staff, Oathkeepers, Occult Staff, Permafrost Prism, Polehammer, Realmbreaker, Rift Glaive, Rootbound Staff, Spiked Gauntlets, Spirithunter, Witchwork Staff | Spiked Gauntlets 1.00 (x1.0), Spirithunter 0.96 (x1.0), Hallowfall 0.96 (x1.9), Permafrost Prism 0.96 (x1.1), Realmbreaker 0.93 (x1.1), Oathkeepers 0.93 (x1.0), Bedrock Mace 0.93 (x1.3), Earthrune Staff 0.89 (x1.0), Lifecurse Staff 0.86 (x1.0), Great Arcane Staff 0.86 (x1.0) |
| 5 | 20: 2 x Bedrock Mace, 2 x Permafrost Prism, Arcane Staff, Damnation Staff, Dawnsong, Earthrune Staff, Exalted Staff, Forgebark Staff, Hallowfall, Hoarfrost Staff, Longbow, Oathkeepers, Occult Staff, Realmbreaker, Rotcaller Staff, Spiked Gauntlets, Spirithunter, Witchwork Staff | Occult Staff 1.00 (x1.1), Permafrost Prism 1.00 (x1.5), Spiked Gauntlets 1.00 (x1.0), Bedrock Mace 1.00 (x1.8), Realmbreaker 0.96 (x1.0), Arcane Staff 0.92 (x1.2), Forgebark Staff 0.92 (x1.0), Witchwork Staff 0.92 (x1.0), Hallowfall 0.92 (x1.3), Exalted Staff 0.89 (x1.0) |
| 6 | 20: 3 x Battle Bracers, 2 x Hallowfall, Blight Staff, Carving Sword, Fallen Staff, Great Arcane Staff, Great Frost Staff, Hammer, Heavy Mace, Mace, Malevolent Locus, Oathkeepers, Realmbreaker, Rootbound Staff, Rotcaller Staff, Shadowcaller, Spiked Gauntlets | Blight Staff 1.00 (x1.0), Hallowfall 1.00 (x2.2), Battle Bracers 1.00 (x2.4), Realmbreaker 0.96 (x1.1), Carving Sword 0.96 (x1.0), Shadowcaller 0.92 (x1.0), Mace 0.92 (x1.0), Spiked Gauntlets 0.88 (x1.0), Heavy Mace 0.80 (x1.1), Rootbound Staff 0.80 (x1.0) |
| 7 | 19: 2 x Bedrock Mace, 2 x Hallowfall, 2 x Permafrost Prism, Arcane Staff, Dawnsong, Earthrune Staff, Great Arcane Staff, Malevolent Locus, Occult Staff, Realmbreaker, Rift Glaive, Rotcaller Staff, Spiked Gauntlets, Spirithunter, Wild Staff, Witchwork Staff | Permafrost Prism 1.00 (x1.4), Spiked Gauntlets 1.00 (x1.0), Bedrock Mace 1.00 (x1.9), Hallowfall 0.96 (x2.0), Malevolent Locus 0.92 (x1.0), Arcane Staff 0.92 (x1.2), Spirithunter 0.92 (x1.1), Occult Staff 0.92 (x1.0), Dawnsong 0.88 (x1.0), Realmbreaker 0.83 (x1.1) |
| 8 | 20: 4 x Hallowfall, 3 x Battle Bracers, Carving Sword, Exalted Staff, Hammer, Heavy Mace, Incubus Mace, Lifecurse Staff, Mace, Malevolent Locus, Permafrost Prism, Realmbreaker, Shadowcaller, Spiked Gauntlets, Spirithunter | Mace 1.00 (x1.1), Hallowfall 1.00 (x2.6), Spiked Gauntlets 1.00 (x1.0), Battle Bracers 1.00 (x3.5), Realmbreaker 0.96 (x1.1), Shadowcaller 0.87 (x1.0), Lifecurse Staff 0.83 (x1.0), Spirithunter 0.83 (x1.0), Hammer 0.74 (x1.0), Incubus Mace 0.74 (x1.0) |
| 9 | 20: 2 x Arcane Staff, 2 x Bedrock Mace, Bloodletter, Damnation Staff, Dawnsong, Earthrune Staff, Energy Shaper, Exalted Staff, Great Frost Staff, Hallowfall, Incubus Mace, Occult Staff, Permafrost Prism, Rampant Staff, Realmbreaker, Spiked Gauntlets, Spirithunter, Witchwork Staff | Witchwork Staff 1.00 (x1.0), Hallowfall 1.00 (x1.1), Incubus Mace 1.00 (x1.0), Spiked Gauntlets 1.00 (x1.0), Occult Staff 0.95 (x1.0), Damnation Staff 0.95 (x1.0), Spirithunter 0.95 (x1.0), Permafrost Prism 0.95 (x1.4), Bedrock Mace 0.95 (x1.7), Dawnsong 0.91 (x1.0) |

The two small multi-guild patterns that remain after the dedupe:

- **Family 4** (28 rosters, 16 guilds, top guild 29%, mostly clap) is a Rift Glaive / Earthrune /
  Lifecurse variant of the meta core.
- **Family 8** (23 rosters, 11 guilds, top guild 30%, mostly brawl) is a brawl lineup on 3.5 Battle
  Bracers, 2.6 Hallowfall and Mace.

Both sit near the 20-roster floor. Of the 3,225 deduped rosters they cover 1.6%.

### Against the anchor pairs

The committed anchor-pair families of the 16+ bucket (1,000 sampled cohorts):

| Anchor family | Anchor pair | Cohorts | Organizations | Battles | Lift | Cast (share of the family's cohorts) |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 0 | Realmbreaker + Spiked Gauntlets | 514 | 45 | 514 | 1.21 | Hallowfall 0.97, Permafrost Prism 0.71, Spirithunter 0.68, Oathkeepers 0.65, Great Arcane Staff 0.53, Earthrune Staff 0.53, Dawnsong 0.50, Bedrock Mace 0.47, Polehammer 0.44, Heavy Mace 0.44, Longbow 0.42 |
| 1 | Dawnsong + Permafrost Prism | 105 | 31 | 105 | 1.32 | Hallowfall 0.89, Earthrune Staff 0.67, Spirithunter 0.55, Longbow 0.49, Blight Staff 0.49, Oathkeepers 0.49, Great Arcane Staff 0.43, Realmbreaker 0.41, Bedrock Mace 0.40 |
| 2 | Oathkeepers + Battle Bracers | 74 | 36 | 73 | 1.31 | Hallowfall 0.91, Heavy Mace 0.58, Mace 0.54, Realmbreaker 0.46 |
| 3 | Galatine Pair + Dreadstorm Monarch | 61 | 22 | 61 | 2.2 | Hallowfall 1.00, Ursine Maulers 0.62, Demonfang 0.62, Damnation Staff 0.57, Oathkeepers 0.47, Hammer 0.47, Nature Staff 0.41 |
| 4 | Malevolent Locus + Hallowfall | 46 | 19 | 46 | 1.23 | Longbow 0.54, Oathkeepers 0.50, Heavy Mace 0.48, Lifecurse Staff 0.46, Mace 0.46, Earthrune Staff 0.41 |
| 5 | Damnation Staff + Hallowfall | 38 | 24 | 38 | 1.21 | Mace 0.50, Oathkeepers 0.45, Longbow 0.45, Great Arcane Staff 0.42 |
| 6 | Longbow + Earthrune Staff | 34 | 16 | 34 | 1.21 | Hallowfall 0.65, Blight Staff 0.62, Realmbreaker 0.47, Mace 0.44, Heavy Mace 0.41 |
| 7 | Longbow + Mace | 29 | 20 | 29 | 1.24 | Hallowfall 0.59, Fallen Staff 0.45, Blight Staff 0.45, Spiked Gauntlets 0.41 |
| 8 | Polehammer + Hallowfall | 24 | 13 | 24 | 1.25 | Heavy Mace 0.46, Permafrost Prism 0.42 |

- **Anchor family 0 is the majority.** Assigning every training roster to its anchor family (first
  match in mined order) puts 5,235 of the 9,598 (55%) in family 0. The other anchors hold 212 to 967
  each; 790 rosters field no anchor pair.
- **Every multi-organization roster family sits inside an existing anchor family.** At t = 0.50 that
  is 13 of the 14 families inside anchor family 0, and the one-guild family 13 inside anchor 3. The
  same holds at every cut, as sets and after the dedupe: the clustering finds no family the anchor
  pairs miss, and only 9 of the 790 rosters that field no anchor pair fall inside a family at t =
  0.50.
- **What it adds is resolution inside anchor family 0.** The 13 families there have medoids 0.33 to
  0.92 apart (median 0.69).
- **The meta family is the anchor family's centre.** Its members sit 0.32 from their own medoid and
  0.33 from the medoid of all 5,235 anchor-0 rosters.
- **The other twelve are distinct lineups.** Their members sit 0.21-0.36 from their own medoid but
  0.44-0.77 from the anchor family's: Longbow-heavy clap lineups, Battle Bracers brawl lineups,
  3 x Great Frost Staff, 2 x Rift Glaive and others.
- **What the anchor display cannot show.** The anchor-pair display gives the anchor pair and its
  cast, the weapons in 40%+ of the anchor family's cohorts. That cast pools these lineups. The meta
  family's rosters field Occult Staff (93%), Witchwork Staff (89%) and Rotcaller Staff (77%), none of
  them in anchor 0's cast. Hallowfall at 2.2 copies and Bedrock Mace at 1.8 copies are not
  expressible there at all.

## Verdict

**Killer-party rosters of 16+ do not form a set of stable families beyond the anchor pairs. They form
one family, and it sits inside the leading anchor pair.**

- **The structure is real.**
  - Rosters sit far closer to their neighbours than sizes, popularity and role balance allow: nearest
    neighbour median 0.20 against 0.50-0.52, and 0.40 against 0.50-0.52 across organizations.
  - Below t = 0.70 the families exist in neither null. They recur on the holdout (30% of holdout
    rosters inside a family radius against 0.3% of seat-null rosters) at a flat rate week by week.
- **It is not a partition.** A forced split has silhouette 0.04-0.11 at every k. The families cover
  10-45% of the rosters depending on the cut, and the rest is a continuum.
- **Most of it is guild repeats.** 72% of nearest neighbours are the same primary guild's roster. At
  t = 0.50, 9 of the 14 families are one guild's lineup, stable because a squad repeats itself: a
  guild, not a family.
- **One family holds everywhere.** The meta lineup at the centre of the Realmbreaker + Spiked
  Gauntlets anchor family:
  - stable under resampling: mean Jaccard 0.75 at t = 0.50, 0.68-0.81 across cuts, 0.79 as sets,
    and 0.71 one roster per guild per day;
  - multi-organization (85 primary guilds at t = 0.50, none above 7%);
  - present every week;
  - recurring on the holdout at its training rate.
  - Every other multi-organization cluster dissolves under resampling, sits at about half one guild,
    or (after the dedupe) is a small pattern near the floor: a Battle Bracers brawl lineup and a Rift
    Glaive variant of the meta core, 23-28 rosters each.
- **A display would add one thing:** the meta family's full lineup with copy counts:
  - 3 x Hallowfall, 2 x Bedrock Mace, Permafrost Prism, Occult Staff, Witchwork Staff, Great Arcane
    Staff, Rotcaller Staff and the rest.
  - The anchor-pair cast misses three of those weapons and every count, because the anchor family
    pools several lineups.
- **Beyond that it would not say more.** The lineups the clustering separates inside the anchor
  family are mostly single guilds' comps. A family display must not present those as families; the
  anchor families' organization gate exists for that reason.
- **Display only.** Nothing here is a scoring input.

## Method note

The measurement scripts ran outside the repository, each against the committed artifacts the Context names; the method above is the whole of what they do.
