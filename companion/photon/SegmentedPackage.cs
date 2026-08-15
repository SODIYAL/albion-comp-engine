using System.Collections;

namespace StatisticsAnalysisTool.PhotonPackageParser;

internal sealed class SegmentedPackage(int totalLength)
{
    // Local edit (2026-08-15): creation stamp for the stale-segment sweep in
    // PhotonParser — see photon/NOTICE.md.
    public DateTime CreatedUtc { get; } = DateTime.UtcNow;

    public int TotalLength { get; } = totalLength;

    public int ReceivedBytesCount { get; set; }

    public byte[] TotalPayload { get; } = new byte[totalLength];

    public BitArray ReceivedBytes { get; } = new(totalLength);
}