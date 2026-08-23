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
- `item_power` stays null: IP only rides the inspect operation (op 148),
  which the companion does not fire passively.

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
place, and their real Q/W picks flow into the loadouts. Toggle in the
connect panel; no re-load, no re-zone. What still needs a zone/visibility
event is the WIRE side (the companion can only report what the game
broadcasts); the remaining wire-side option is parsing the inspect
response (op 148) so a manual in-game inspect refreshes any member — needs
a live /schema capture of that response's shape first (inspect someone with
the companion running and check /schema responses).

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
