using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;

namespace CompForgeCompanion;

/// <summary>
/// Raw-socket packet capture (SAT's SocketsPacketProvider approach): one
/// promiscuous raw IP socket per local IPv4 interface, filter UDP ports
/// 5055/5056/5058 (Albion Photon), REASSEMBLE IP fragments, forward complete
/// Photon payloads to the parser. Requires Administrator on Windows — no
/// Npcap dependency. Read-only: nothing is ever sent.
///
/// IP reassembly is load-bearing: Albion sends game messages larger than one
/// datagram, the OS fragments them, and a lone fragment is not a valid Photon
/// packet — feeding one produces "Type code: N not implemented" as the parser
/// reads misaligned bytes. That was v0.1's zero-events bug.
/// </summary>
public sealed class RawSocketCapture
{
    private static readonly int[] AlbionPorts = { 5055, 5056, 5058 };
    private readonly AlbionEventParser _parser;
    private readonly FragmentReassembler _reasm = new();
    // One capture thread runs per interface (VPN/Hyper-V adapters included),
    // but the parser's internal state (fragment reassembly, guid maps) is not
    // thread-safe — all ReceivePacket calls are serialized through this lock.
    // Game traffic rides one interface, so contention is nil.
    private readonly object _parserLock = new();
    public long PacketsSeen, AlbionPackets, ParseErrors, Fragments, Reassembled;
    public string? LastParseError;

    public RawSocketCapture(AlbionEventParser parser) => _parser = parser;

    public void Start()
    {
        var addrs = NetworkInterface.GetAllNetworkInterfaces()
            .Where(n => n.OperationalStatus == OperationalStatus.Up
                        && n.NetworkInterfaceType != NetworkInterfaceType.Loopback)
            .SelectMany(n => n.GetIPProperties().UnicastAddresses)
            .Where(a => a.Address.AddressFamily == AddressFamily.InterNetwork)
            .Select(a => a.Address)
            .Distinct()
            .ToList();
        if (addrs.Count == 0)
            throw new InvalidOperationException("no active IPv4 interfaces found");

        foreach (var addr in addrs)
        {
            var t = new Thread(() => Listen(addr)) { IsBackground = true, Name = $"capture-{addr}" };
            t.Start();
        }
        Console.WriteLine($"[capture] listening on {addrs.Count} interface(s): {string.Join(", ", addrs)}");
    }

    private void Listen(IPAddress addr)
    {
        Socket socket;
        try
        {
            socket = new Socket(AddressFamily.InterNetwork, SocketType.Raw, ProtocolType.IP);
            socket.Bind(new IPEndPoint(addr, 0));
            socket.SetSocketOption(SocketOptionLevel.IP, SocketOptionName.HeaderIncluded, true);
            // SIO_RCVALL — promiscuous mode; the call that needs Administrator
            socket.IOControl(IOControlCode.ReceiveAll, BitConverter.GetBytes(1), null);
        }
        catch (SocketException e)
        {
            Console.WriteLine($"[capture] {addr}: {e.Message}");
            Console.WriteLine("[capture] raw sockets need Administrator — right-click, 'Run as administrator'.");
            return;
        }

        var buf = new byte[65535];
        while (true)
        {
            int n;
            try { n = socket.Receive(buf); }
            catch (SocketException) { continue; }
            Interlocked.Increment(ref PacketsSeen);
            HandleIpPacket(buf, n);
        }
    }

    /// <summary>Parse the IPv4 header, reassemble if fragmented, and when a
    /// full datagram is in hand hand its UDP payload to the parser.</summary>
    private void HandleIpPacket(byte[] buf, int len)
    {
        if (len < 20 || (buf[0] >> 4) != 4) return;
        var ihl = (buf[0] & 0x0F) * 4;
        if (ihl < 20 || len < ihl) return;
        if (buf[9] != 17) return;                        // UDP only
        var totalLen = (buf[2] << 8) | buf[3];
        if (totalLen < ihl || totalLen > len) totalLen = len;   // trust the smaller
        var ipPayloadLen = totalLen - ihl;
        if (ipPayloadLen <= 0) return;

        var id = (buf[4] << 8) | buf[5];
        var flagsFrag = (buf[6] << 8) | buf[7];
        var moreFragments = (flagsFrag & 0x2000) != 0;
        var fragOffset = (flagsFrag & 0x1FFF) * 8;
        var src = BitConverter.ToInt32(buf, 12);
        var dst = BitConverter.ToInt32(buf, 16);

        byte[] ipPayload;
        if (!moreFragments && fragOffset == 0)
        {
            // Filter BEFORE copying: this promiscuous socket sees every UDP
            // datagram on the host (voice, streams, browsers) — copying each
            // one just to drop it at the port check below was steady GC churn.
            if (ipPayloadLen < 8) return;
            var sp = (buf[ihl] << 8) | buf[ihl + 1];
            var dp = (buf[ihl + 2] << 8) | buf[ihl + 3];
            if (!AlbionPorts.Contains(sp) && !AlbionPorts.Contains(dp)) return;
            ipPayload = new byte[ipPayloadLen];
            Array.Copy(buf, ihl, ipPayload, 0, ipPayloadLen);
        }
        else
        {
            Interlocked.Increment(ref Fragments);
            var part = new byte[ipPayloadLen];
            Array.Copy(buf, ihl, part, 0, ipPayloadLen);
            var whole = _reasm.Add(src, dst, id, fragOffset, part, moreFragments);
            if (whole == null) return;                   // still waiting on pieces
            Interlocked.Increment(ref Reassembled);
            ipPayload = whole;
        }

        // ipPayload now starts at the UDP header
        if (ipPayload.Length < 8) return;
        var sport = (ipPayload[0] << 8) | ipPayload[1];
        var dport = (ipPayload[2] << 8) | ipPayload[3];
        if (!AlbionPorts.Contains(sport) && !AlbionPorts.Contains(dport)) return;
        var udpLen = (ipPayload[4] << 8) | ipPayload[5];
        var photonLen = Math.Min(udpLen - 8, ipPayload.Length - 8);
        if (photonLen <= 0) return;
        var photon = new byte[photonLen];
        Array.Copy(ipPayload, 8, photon, 0, photonLen);

        Interlocked.Increment(ref AlbionPackets);
        try { lock (_parserLock) _parser.ReceivePacket(photon); }
        catch (Exception e)
        {
            Interlocked.Increment(ref ParseErrors);
            LastParseError = e.Message;
        }
    }

    /// <summary>Minimal IPv4 datagram reassembler, keyed by (src, dst, id).
    /// Holds fragments until the datagram is contiguous 0..total, then emits
    /// the joined IP payload. Sweeps incomplete datagrams older than 5s so a
    /// dropped fragment can't leak memory.</summary>
    private sealed class FragmentReassembler
    {
        private sealed class Entry
        {
            public readonly SortedDictionary<int, byte[]> Parts = new();
            public int? TotalLen;
            public readonly DateTime FirstSeen = DateTime.UtcNow;
        }

        private readonly Dictionary<(int src, int dst, int id), Entry> _entries = new();
        private DateTime _lastSweep = DateTime.UtcNow;

        public byte[]? Add(int src, int dst, int id, int offset, byte[] data, bool moreFragments)
        {
            var key = (src, dst, id);
            lock (_entries)
            {
                Sweep();
                if (!_entries.TryGetValue(key, out var e))
                    _entries[key] = e = new Entry();
                e.Parts[offset] = data;
                if (!moreFragments) e.TotalLen = offset + data.Length;
                if (e.TotalLen is not int total) return null;

                // contiguous from 0 to total?
                var pos = 0;
                foreach (var kv in e.Parts)
                {
                    if (kv.Key > pos) return null;       // gap — keep waiting
                    pos = Math.Max(pos, kv.Key + kv.Value.Length);
                }
                if (pos < total) return null;

                var outbuf = new byte[total];
                foreach (var kv in e.Parts)
                {
                    var copyLen = Math.Min(kv.Value.Length, total - kv.Key);
                    if (copyLen > 0) Array.Copy(kv.Value, 0, outbuf, kv.Key, copyLen);
                }
                _entries.Remove(key);
                return outbuf;
            }
        }

        private void Sweep()
        {
            if (DateTime.UtcNow - _lastSweep < TimeSpan.FromSeconds(2)) return;
            _lastSweep = DateTime.UtcNow;
            var cutoff = DateTime.UtcNow - TimeSpan.FromSeconds(5);
            foreach (var k in _entries.Where(kv => kv.Value.FirstSeen < cutoff)
                         .Select(kv => kv.Key).ToList())
                _entries.Remove(k);
        }
    }
}
