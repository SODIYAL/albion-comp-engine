using System.Buffers;

// Vendored from Statistics Analysis Tool (Triky313/AlbionOnline-StatisticsAnalysis,
// GPL-3.0) — the only working Albion Protocol18 parser. See photon/NOTICE.md.
namespace StatisticsAnalysisTool.Abstractions;

public interface IPhotonReceiver
{
    void ReceivePacket(byte[] payload);
    void ReceivePacket(ReadOnlySpan<byte> payload);
    void ReceivePacket(ReadOnlySequence<byte> payload);
}
