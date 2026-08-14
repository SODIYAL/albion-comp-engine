using System.Xml.Linq;

namespace CompForgeCompanion;

/// <summary>
/// Spell index -> UniqueName, from ao-bin-dumps' raw spells.xml. The packet's
/// spell index is a position in the game's flat spell list, which is the XML's
/// child elements IN DOCUMENT ORDER with a specific counting rule (verified
/// against a live party, matches SAT's SpellData.BuildSpells):
///   - colortag        : skipped (no index)
///   - passivespell    : +1
///   - activespell     : +1, and +1 MORE if it has a channelingspell child
///   - togglespell     : +1
/// The grouped spells.json loses the interleaved order, so we parse the raw
/// XML. Downloaded on first run, cached beside the exe, refreshed after 7 days
/// (spell indices shift with patches — same staleness risk as items/events).
/// Resolved names match the sheet evidence IDs (HOLYFLASH, CELESTIAL_SPHERE, …)
/// so Comp Forge can score each player's ACTUAL Q/W/E, not the line default.
/// </summary>
public sealed class SpellDb
{
    private const string SourceUrl =
        "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/spells.xml";

    private readonly List<string> _byIndex = new();
    public int Count => _byIndex.Count;

    public static async Task<SpellDb> LoadAsync(string cacheDir)
    {
        var db = new SpellDb();
        var cache = Path.Combine(cacheDir, "spells.xml");
        string? xml = null;

        var fresh = File.Exists(cache)
            && DateTime.UtcNow - File.GetLastWriteTimeUtc(cache) < TimeSpan.FromDays(7);
        if (fresh)
            xml = await File.ReadAllTextAsync(cache);
        else
        {
            try
            {
                using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(60) };
                http.DefaultRequestHeaders.UserAgent.ParseAdd("compforge-companion/0.1");
                xml = await http.GetStringAsync(SourceUrl);
                await File.WriteAllTextAsync(cache, xml);
                Console.WriteLine($"[spells] refreshed from ao-bin-dumps ({xml.Length / 1024 / 1024} MB)");
            }
            catch (Exception e) when (File.Exists(cache))
            {
                Console.WriteLine($"[spells] refresh failed ({e.Message}) — using stale cache");
                xml = await File.ReadAllTextAsync(cache);
            }
            catch (Exception e)
            {
                Console.WriteLine($"[spells] WARNING: no spell table ({e.Message}) — raw indices only");
            }
        }

        if (xml != null) db.Parse(xml);
        Console.WriteLine($"[spells] {db.Count} spell indices loaded");
        return db;
    }

    private void Parse(string xml)
    {
        var root = XDocument.Parse(xml).Root;
        if (root == null) return;
        foreach (var el in root.Elements())
        {
            var name = (string?)el.Attribute("uniquename") ?? "";
            switch (el.Name.LocalName)
            {
                case "colortag":
                    break;                                   // no index
                case "passivespell":
                case "togglespell":
                    _byIndex.Add(name);
                    break;
                case "activespell":
                    _byIndex.Add(name);
                    if (el.Element("channelingspell") != null) _byIndex.Add(name);
                    break;
            }
        }
    }

    /// <summary>Spell UniqueName for a packet index, or null if out of range.</summary>
    public string? Name(int index) =>
        index >= 0 && index < _byIndex.Count ? _byIndex[index] : null;
}
