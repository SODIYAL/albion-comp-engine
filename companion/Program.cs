using System.Net;
using System.Text;
using CompForgeCompanion;

/* Comp Forge Party Companion — read-only local Photon reader.
 *
 * Extracts party roster + per-member equipment and selected spells from the
 * data the game client already renders (party UI, inspect window) and
 * serves it as JSON on localhost for Comp Forge's "connect companion"
 * button. Scope, event map and legality reasoning: ../COMPANION_SCOPE.md.
 *
 *   usage: compforge-companion [--port 53321] [--debug]
 *   endpoints: GET /party  GET /status
 *
 * Read-only by construction: the capture socket never sends; the HTTP
 * server binds loopback only.
 */

var port = 53321;
var debug = false;
for (var i = 0; i < args.Length; i++)
{
    if (args[i] == "--port" && i + 1 < args.Length && int.TryParse(args[i + 1], out var p)) port = p;
    if (args[i] == "--debug") debug = true;
}

Console.WriteLine("Comp Forge Party Companion v0.1 (calibration build)");
Console.WriteLine("read-only Photon reader — party roster, equipment, spell picks");
Console.WriteLine();

var exeDir = AppContext.BaseDirectory;
var items = await ItemDb.LoadAsync(exeDir);
var spells = await SpellDb.LoadAsync(exeDir);
var state = new PartyState();
state.SetSpellDb(spells);
state.EnablePersistence(Path.Combine(exeDir, "party-cache.json"));
var parser = new AlbionEventParser(state, items, debug);
var capture = new RawSocketCapture(parser);
capture.Start();

var listener = new HttpListener();
listener.Prefixes.Add($"http://127.0.0.1:{port}/");
listener.Prefixes.Add($"http://localhost:{port}/");
listener.Start();
Console.WriteLine($"[http] serving http://localhost:{port}/party  (and /status)");
Console.WriteLine("[http] CORS: any origin (loopback-only server; data is party-scope only)");
if (!debug) Console.WriteLine("tip: --debug prints every handled event — use it for the first live run");

var started = DateTime.UtcNow;
while (true)
{
    HttpListenerContext ctx;
    try { ctx = await listener.GetContextAsync(); }
    catch (Exception) { break; }

    var res = ctx.Response;
    res.Headers["Access-Control-Allow-Origin"] = "*";
    res.Headers["Cache-Control"] = "no-store";

    string body;
    switch (ctx.Request.Url?.AbsolutePath)
    {
        case "/party":
            body = state.ToJson();
            res.ContentType = "application/json";
            break;
        case "/schema":
            // parameter-shape map per event/op code — used to identify which
            // codes carry party/equipment data on the current game version
            body = System.Text.Json.JsonSerializer.Serialize(parser.SchemaDump(),
                new System.Text.Json.JsonSerializerOptions { WriteIndented = true });
            res.ContentType = "application/json";
            break;
        case "/status":
            body = System.Text.Json.JsonSerializer.Serialize(new
            {
                ok = true,
                version = "0.1",
                uptime_s = (int)(DateTime.UtcNow - started).TotalSeconds,
                packets_seen = capture.PacketsSeen,
                albion_packets = capture.AlbionPackets,
                fragmented_packets = capture.Fragments,
                reassembled_datagrams = capture.Reassembled,
                parse_errors = capture.ParseErrors,
                last_parse_error = capture.LastParseError,
                photon_events = parser.EventsSeen,
                photon_requests = parser.RequestsSeen,
                photon_responses = parser.ResponsesSeen,
                handled_events = parser.EventsHandled,
                detected_codes = parser.Bindings(),   // role -> code, self-calibrated this session
                event_code_histogram = parser.TopEventCodes(15),
                last_event_utc = parser.LastEventUtc == DateTime.MinValue ? null : parser.LastEventUtc.ToString("o"),
                party_members = state.Count,
                item_indices = items.Count,
                spell_indices = spells.Count,
            }, new System.Text.Json.JsonSerializerOptions { WriteIndented = true });
            res.ContentType = "application/json";
            break;
        default:
            body = "compforge-companion: GET /party, /status, or /schema\n";
            res.ContentType = "text/plain";
            break;
    }

    var bytes = Encoding.UTF8.GetBytes(body);
    res.ContentLength64 = bytes.Length;
    await res.OutputStream.WriteAsync(bytes);
    res.Close();
}
