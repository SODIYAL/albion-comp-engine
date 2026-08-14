# Comp Forge Party Companion

A small **read-only** Windows console app that reads what your Albion client
already shows you — your party roster, and the equipment + selected spells of
players in your zone — and serves it as JSON on `localhost` so Comp Forge can
auto-fill a comp from your real party.

It never sends anything to the game and never automates gameplay. It reads the
same data the party UI and the inspect window already render on your screen —
the tolerated category (like Statistics Analysis Tool), not radar. Full scope,
event map, and legality reasoning: [../COMPANION_SCOPE.md](../COMPANION_SCOPE.md).

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
- **Item indices** — refreshed automatically from `ao-bin-dumps` on first run
  and every 7 days (cached as `items.txt` beside the exe). Delete the cache to
  force a refresh.
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
