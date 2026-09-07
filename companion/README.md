# Comp Forge Party Companion

A small **read-only** Windows console app that reads what your Albion client
already shows you — your party roster, and the equipment + selected spells of
players in your zone — and serves it as JSON on `localhost` so Comp Forge can
auto-fill a comp from your real party.

It never sends anything to the game and never automates gameplay. It reads the
same data the party UI and the inspect window already render on your screen —
the tolerated category (like Statistics Analysis Tool), not radar. Full scope,
event map, and legality reasoning: [../COMPANION_SCOPE.md](../COMPANION_SCOPE.md).

## Status — LIVE-CONFIRMED (2026-08-23, owner's in-game run)

The one live run happened, in an 11-member party on the current patch:

- **Capture + parsing**: 2,973 Albion packets, 5,909 Photon events, 339
  handled, **0 parse errors** in 89s — the vendored Protocol18 parser is
  current.
- **Shape-based auto-calibration**: all four roles detected on the current
  game version (`NewCharacter:29, SelfJoin:2, EquipmentChanged:90,
  PartyRoster:231`) with no hand re-mapping after the patches since the
  build — the self-healing design works.
- **Spell-name resolution**: an in-zone member resolved to full names
  matching the engine's sheet evidence IDs (`q: ARCANE_CHAIN_MISSILE,
  w: ENIGMA_BLADE, e: BLACKHOLE, d: HASTE, r: ENERGY_BARRIER`), with full
  tier+enchant equipment (`T6_MAIN_ARCANESTAFF_UNDEAD@1`).
- **Roster**: all 11 members listed; self detected with weapon.

Expected-by-design behavior seen in the run (not bugs):

- Out-of-zone members are name-only until they come near (visibility rule).
- Your OWN equipment shows empty until you swap any gear piece once —
  self-gear arrives on the change event.
- `item_power` stays null until someone is INSPECTED: IP only rides the
  inspect response, which the companion never fires itself — see "Inspect
  refresh" below.

**End-to-end CONFIRMED same day (second run):** Comp Forge's **connect live
party** → **load party into comp** worked against the live companion — a
real 7-member party listed with 7/7 known weapons and loaded into the comp
("This party: 7 curated, 0 illustrative"), with the observed-cohort
affinity strip firing on the loaded roster. Known friction, by design: it
takes a load or two plus zoning for every member's weapon to populate,
because weapons only arrive as members become VISIBLE (the visibility
rule). SHIPPED same day as **live sync** (owner request: "as current as
possible"): after a load, every companion poll auto-merges into the comp —
newly visible weapons fill in, a member's weapon swap updates their slot in
place, and their real Q/W picks flow into the loadouts — and since
2026-09-06 so does their WORN KIT: every curated piece the companion
reports (head/chest/shoes/cape/off-hand/potion/food) lands in the member's
loadout, so the dressed score the page shows is their real build, and an
inspect that refreshes gear re-dresses them on the next poll. Pieces the
catalogue does not curate (a plain cape, most food) stay unset — the page
never invents a stand-in. The live panel shows `kit n/7` and item power
per member. Toggle in the
connect panel; no re-load, no re-zone. What still needs a zone/visibility
event is the WIRE side (the companion can only report what the game
broadcasts). The wire-side escape hatch SHIPPED 2026-09-06: the companion
parses the INSPECT response, so a manual in-game inspect refreshes any
party member on demand — yourself included, which closes the "own gear is
empty until you swap" gap. Shape taken from SAT's
`GetCharacterEquipmentResponse` (guid, 10-slot equipment, item power),
matched by shape like every other handler; NOT yet confirmed against a live
capture on the current patch — the first inspect with `--debug` on is the
confirmation (see "Inspect refresh").

## Inspect refresh (on-demand, 2026-09-06)

Right-click a party member in game -> **Inspect**. The server answers with
their CURRENT loadout using real item type ids, whether or not they are
visible to you, and the companion records it (`"source": "Inspect"`,
`item_power` filled). Inspect yourself and your own gear appears without
swapping anything.

- Attribution is by **guid**, which only the party roster event carries: the
  target must be in your party, and a roster event must have listed them
  (zone once after joining). A stranger's inspect matches nobody and is
  dropped — party scope holds.
- `/status` -> `detected_codes.Inspect` appears after the first successful
  inspect (SAT lists the op as 148; the companion binds whatever number
  carries the shape this patch). If it never appears while `--debug` prints
  nothing for the inspect, the response shape has changed: look it up under
  `/schema` -> `responses` (a `guid(byte[16])` at 0 next to a `short[10]`)
  and adjust `LooksLikeInspect`.
- Spells: SAT does not read spells off this response. The companion takes a
  14-slot array if the wire carries one; otherwise the member keeps the
  Q/W/E they last broadcast. Whether it is there is unverified — `--debug`
  prints `sp=14` when it is, `sp=` when it is not.

Everything below is the full run/troubleshooting reference.

## Run it

Needs the [.NET 8 SDK](https://dotnet.microsoft.com/download) to build.

```
cd companion
dotnet build -c Release
```

Then run the exe **as Administrator** (raw-socket capture needs it — no Npcap
required):

```
# right-click bin\Release\net8.0\compforge-companion.exe -> Run as administrator
# or from an elevated terminal:
bin\Release\net8.0\compforge-companion.exe --debug
```

`--debug` prints every handled event — use it for your first live run so you
can confirm party/equipment/spell events are being parsed. Drop it once it
works. `--port N` changes the port (default 53321).

## What it serves

- `GET http://localhost:53321/party` — the live party:

  ```json
  {
    "ts": "2026-08-13T19:20:00Z",
    "self": "YourName",
    "members": [
      { "name": "Alstroameria", "weapon": "2H_HOLYSTAFF",
        "weapon_item": "T5_2H_HOLYSTAFF@1", "item_power": 796,
        "equipment": { "head": "T6_HEAD_CLOTH_SET1", "chest": "…", "shoes": "…", "cape": "…" },
        "spells": { "q": "HOLY_GENERIC_HEAL", "w": "SACRED_PULSE",
                    "e": "HOLY_BEAM_AVALON" },
        "source": "EquipmentChanged" }
    ]
  }
  ```

  `source` names the last message that touched the member: `PartyRoster`
  (name only), `NewCharacter` / `EquipmentChanged` (visibility broadcasts),
  `Inspect` (an on-demand in-game inspect — the only source of `item_power`),
  `cache` (restored roster, no gear yet).

  `weapon` is the engine `unique_name` (matches the Comp Forge dataset);
  `spells` are resolved server-side from raw indices to spell UniqueNames per
  slot (Q/W/E/D/R/F) so they match the engine's sheet evidence IDs. A member
  appears the moment they're in your party; their loadout fills in as they
  become visible or change gear.

  Known limitation: the game's object ids are per-zone and there is no clean
  zone-change signal, so a reused id can briefly attribute a nearby player's
  gear to a party member with the same stale id — it self-corrects on that
  member's next visibility (NewCharacter) event. The id map is bounded
  (4096 entries) so long sessions don't grow it forever.

- `GET http://localhost:53321/status` — health: packets seen, Albion packets,
  events parsed, party size, item-table size. Use it to confirm capture is
  live before trusting `/party`.

## First-run checklist

1. Run as Administrator, with `--debug`.
2. `/status` should show `item_indices` in the thousands.
3. Get in a party and load into a zone. `albion_packets` and `photon_events`
   in `/status` should start climbing.
4. `--debug` output should print `PartyJoined`, `NewCharacter`,
   `EquipmentChanged` lines. If Albion packets climb but nothing is *handled*,
   the event codes have likely shifted — see below.

## Patch ritual (important)

Albion's Photon event codes are **positional and shift with game patches**.
Two things can go stale after an update:

- **Event codes** in `AlbionEventParser.cs` (the `Ev*`/`Op*` constants). If
  `/status` shows Albion packets flowing but `handled_events` stuck at 0,
  re-sync these against SAT's `EventCodes.cs`
  (`Triky313/AlbionOnline-StatisticsAnalysis`, `src/StatisticsAnalysisTool/Network/EventCodes.cs`).
- **Item and spell indices** — refreshed automatically from `ao-bin-dumps` on
  first run and every 7 days (cached beside the exe as `items.txt` and
  `spells.xml`). Delete a cache file to force a refresh. Spell indices are a
  position in the game's flat spell list (document order of `spells.xml`,
  colortag skipped, channeling spells taking an extra slot); if resolved spell
  names look wrong after a patch, delete `spells.xml` to re-download.
- **The Protocol18 parser itself** (`photon/`) can drift if Albion changes its
  wire encoding. If a future patch brings back `Type code: N not implemented`
  in `--debug`, re-vendor `photon/` from the current SAT source (see
  `photon/NOTICE.md` for the exact files).

`--debug` prints a raw parameter-shape dump when a party event arrives without
the expected fields — that dump is what you (or a future patch-fix) use to find
the new indices.

## Design notes

- **Protocol18 parser (vendored, GPL-3.0)**: current Albion serializes Photon
  messages with "Protocol18"; the stock `PhotonPackageParser` NuGet only speaks
  the older "Protocol16" and silently decodes nothing (the original zero-events
  bug — every data packet threw `Type code: N not implemented`). The working
  parser is vendored under `photon/` from Statistics Analysis Tool. This makes
  the **companion binary** GPL-3.0; Comp Forge (the web app) is unaffected — it
  only talks to us over localhost HTTP. See [photon/NOTICE.md](photon/NOTICE.md).
- **Party scope only**: equipment/spell updates are recorded only for players
  who are in your party (or you). Randoms in the zone are ignored.
- **Windows only**: the capture stack (promiscuous raw socket, `SIO_RCVALL`)
  is Windows-specific by design.
