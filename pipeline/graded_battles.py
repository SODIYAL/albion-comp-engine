"""The battles a graded validation round has shown.

A battle on this list is never sampled into a later form: its rosters
were shown to graders and pinned, so they are train under standing rule
16 (tests/VALIDATION.md). Every form generator reads this one list:
pipeline/audit_style_rosters.py (the roster rounds),
tests/tier2_blindtest.py generate (the V3 next-pick forms, which also
exclude every battle the answer key of an earlier V3 round records) and
pipeline/style_blind_round.py generate (the style-labelling forms, which
also exclude every battle an earlier round's key, V3 or style-labelling,
records). A roster round's battles, and a style-labelling form's
harvested battles, join the list when the round is graded.
"""

# validation round 1 (ten rosters) + round 2 (twenty): both graded and
# pinned in test_golden T34 / T36; never re-sampled into a form
GRADED_BATTLES = [1439261314, 1439270346, 1439324226, 1439336518, 1439380503, 1442341916, 1442399167, 1442450338, 1443149088,
                  1439323062, 1439423672, 1442916379, 1442381572, 1443149032, 1442340579, 1443089499, 1439330397,
                  1439163242, 1442365275, 1442813939, 1443067935, 1443196794, 1442359908, 1442270050, 1442373560,
                  1439247869, 1439330979, 1439276629,
                  # round 3 (the 10-14 band, rosters 1-11 called; T39)
                  1439331464, 1442240282, 1442879983, 1442360406, 1443108045, 1442343192, 1442339162, 1443074329, 1439338826, 1439172287, 1442358198,
                  # round 4 (the 10-14 band, all twenty graded; T43)
                  1439334286, 1442250301, 1442972989, 1442398268, 1443176864, 1442349353, 1442348698, 1443926164, 1443148724, 1439351476,
                  1439174574, 1443907529, 1442378155, 1443767342, 1442865547, 1443867507, 1443110811, 1443257154, 1442366915, 1442294064]
