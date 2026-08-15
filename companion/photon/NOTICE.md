# Vendored Photon Protocol18 parser

The files in this `photon/` directory are vendored from **Statistics Analysis
Tool** (<https://github.com/Triky313/AlbionOnline-StatisticsAnalysis>),
licensed **GPL-3.0**. They implement Albion Online's current Photon message
encoding ("Protocol18"), which the stock `PhotonPackageParser` NuGet package
(Protocol16 only) cannot decode — that mismatch was the companion's
zero-events bug.

Source subprojects:

- `StatisticsAnalysisTool.PhotonPackageParser/` → `PhotonParser.cs`,
  `CommandType.cs`, `MessageType.cs`, `SegmentedPackage.cs`
- `StatisticsAnalysisTool.Protocol18/` → `Protocol18Deserializer.cs`,
  `Protocol18Stream.cs`, `Protocol18Type.cs`, `Photon/*.cs`
- `StatisticsAnalysisTool.Abstractions/IPhotonReceiver.cs`

Local edits: removed the `StatisticsAnalysisTool.Diagnostics.DebugConsole`
logging calls from `PhotonParser.cs` (three lines) so the files stand alone;
namespaces are otherwise unchanged. Hardening pass (2026-08-15, code review):
`PhotonParser.cs` gained a `totalLength` sanity cap and a periodic sweep of
stranded fragment reassembly buffers (raw-socket capture drops packets, so
incomplete trains otherwise leak), and its CRC branch now reads the CRC from
the CRC field (it read bytes 0-3 — header bytes — before) and compares
unsigned; `SegmentedPackage.cs` gained the `CreatedUtc` stamp the sweep uses.

## License consequence

Because this code is GPL-3.0, the **companion executable** built from this
project is a GPL-3.0 derivative work. That is fine for personal/guild use;
if you distribute the binary, provide its source (this repo).

**Comp Forge (the web app) is NOT affected.** It communicates with the
companion only over a localhost HTTP boundary (JSON), which is not linking —
so the web product does not become a GPL derivative.

To keep the companion under a permissive license instead, Protocol18 would
have to be reimplemented clean-room (no code copied from SAT).
