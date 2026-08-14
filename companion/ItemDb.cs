using System.Text.RegularExpressions;

namespace CompForgeCompanion;

/// <summary>
/// Item index -> name mapping, from ao-bin-dumps' formatted/items.txt
/// (lines: "  123: T8_2H_MACE@3    : Elder's Heavy Mace"). Downloaded on
/// first run and cached beside the exe; the cache is refreshed when older
/// than 7 days (game patches shift indices — same staleness risk as the
/// event codes, see COMPANION_SCOPE.md). Offline + no cache = raw indices
/// are reported as "ITEM_12345" so the companion still runs, loudly.
/// </summary>
public sealed class ItemDb
{
    private const string SourceUrl =
        "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/formatted/items.txt";
    private static readonly Regex Line = new(@"^\s*(\d+)\s*:\s*(\S+)\s*(?::|$)", RegexOptions.Compiled);

    private readonly Dictionary<int, string> _byIndex = new();
    public int Count => _byIndex.Count;

    public static async Task<ItemDb> LoadAsync(string cacheDir)
    {
        var db = new ItemDb();
        var cache = Path.Combine(cacheDir, "items.txt");
        string? text = null;

        var fresh = File.Exists(cache)
            && DateTime.UtcNow - File.GetLastWriteTimeUtc(cache) < TimeSpan.FromDays(7);
        if (fresh)
            text = await File.ReadAllTextAsync(cache);
        else
        {
            try
            {
                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
                http.DefaultRequestHeaders.UserAgent.ParseAdd("compforge-companion/0.1");
                text = await http.GetStringAsync(SourceUrl);
                await File.WriteAllTextAsync(cache, text);
                Console.WriteLine($"[items] refreshed from ao-bin-dumps ({text.Length / 1024} KB)");
            }
            catch (Exception e) when (File.Exists(cache))
            {
                Console.WriteLine($"[items] refresh failed ({e.Message}) — using stale cache");
                text = await File.ReadAllTextAsync(cache);
            }
            catch (Exception e)
            {
                Console.WriteLine($"[items] WARNING: no item table ({e.Message}) — raw indices only");
            }
        }

        if (text != null)
            foreach (var line in text.Split('\n'))
            {
                var m = Line.Match(line);
                if (m.Success)
                    db._byIndex[int.Parse(m.Groups[1].Value)] = m.Groups[2].Value;
            }
        Console.WriteLine($"[items] {db.Count} item indices loaded");
        return db;
    }

    /// <summary>Full item string incl. tier + enchant, e.g. "T8_2H_MACE@3".</summary>
    public string FullName(int index) =>
        _byIndex.TryGetValue(index, out var n) ? n : $"ITEM_{index}";

    /// <summary>Engine unique_name: strip tier prefix and @enchant suffix —
    /// the same normalization pipeline/sample_battles.py applies to
    /// killboard item types ("T8_2H_MACE@3" -> "2H_MACE").</summary>
    public static string ToEngineKey(string fullName)
    {
        var s = fullName;
        var at = s.IndexOf('@');
        if (at >= 0) s = s[..at];
        s = Regex.Replace(s, @"^T\d+_", "");
        return s;
    }
}
