# Comp Forge Party Companion

A small **read-only** Windows console app that reads what your Albion client
already shows you — your party roster, and the equipment + selected spells of
players in your zone — and serves it as JSON on `localhost` so Comp Forge can
auto-fill a comp from your real party.

It never sends anything to the game and never automates gameplay. It reads the
same data the party UI and the inspect window already render on your screen —
the tolerated category (like Statistics Analysis Tool), not radar. Full scope,
event map, and legality reasoning: [../COMPANION_SCOPE.md](../COMPANION_SCOPE.md).

## Status — pick up here (2026-08-14)

**WORKING and live-verified against a real 5-person party:** party roster,
each member's name/guild, weapon (as the engine's `unique_name`), full
tier+enchant equipment. Members outside your zone correctly show name-only.

**BUILT, not yet live-verified:** spell-name resolution — `/party` spells now
resolve to UniqueNames (`HOLYFLASH`, `CELESTIAL_SPHERE`, …) that match the
engine's sheet evidence IDs. Validated by index math against the last live
party; needs one in-game run to confirm the resolved names look right.

**NOT STARTED:** the Comp Forge "connect companion" button — poll `/party`,
drop each member's weapon into a slot, forge around the real party. This is
the last piece; the data it needs (weapons) already works perfectly.

**To resume: verify spells, then build the button.**

1. Close any running companion window; double-click `run-companion.bat` → Yes.
2. First launch downloads `spells.xml` (~9 MB, once) — watch for
   `[spells] 9216 spell indices loaded` in the console.
3. In a zone with a party member visible, open `http://localhost:53321/party`
   and confirm `spells` shows names (not numbers), e.g. Redemption Staff →
   `q:"HOLYFLASH" w:"HEALINGBEAM" e:"CELESTIAL_SPHERE"`.
4. If names look wrong, delete `spells.xml` to re-pull, or re-run the
   `/schema` discovery (below) — spell indices shift per patch.

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
        "spells": { "q": 12, "w": 34, "e": 56, "d": 78, "r": 90, "f": 11 },
        "source": "EquipmentChanged" }
    ]
  }
  ```

  `weapon` is the engine `unique_name` (matches the Comp Forge dataset);
  `spells` are raw spell indices per slot (Q/W/E/D/R/F) — the page resolves
  them to names. A member appears the moment they're in your party; their
  loadout fills in as they become visible or change gear.

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
