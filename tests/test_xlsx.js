/* Workbook reader tests - dashboard/_import.js, the Excel half.
 *
 * The account modules run in a vm context with no document, as the page
 * loads them (tests/test_import.js does the same). Every workbook here is
 * built by the test itself: a zip writer (local headers, the central
 * directory, the end record; entries stored or deflated through
 * CompressionStream("deflate-raw"), each with its CRC-32 from zlib, never
 * the module's own) packs the parts a workbook carries. Nothing is read
 * from disk but the dataset's catalog, which the detection runs over.
 *
 * Pinned: what a file's bytes are (a zip, an Office compound file, text)
 * and a text file's encoding; the zip's directory, stored and deflated
 * entries, every entry checked against its size and CRC; the workbook's
 * sheets in tab order (worksheets alone, a hidden one marked, the one
 * open when saved first) through the package's and the workbook's
 * relationships; shared strings (rich runs, the phonetic guide left out,
 * escapes, entities); a sheet's cells (shared and inline strings,
 * numbers in their shortest form, booleans, an error read empty, a
 * formula's saved result, gaps kept so the letters stay the sheet's,
 * cells and rows without references, a merged range read in its top-left
 * cell); the bounds (rows, columns, characters, the entries, a part and
 * the file); the cells written into the paste box and read back to the
 * same cells, and the same rows a paste of them gives; every refusal (a
 * damaged zip, a bad CRC, a bad deflate, a password, an .xls, a zip that
 * is no workbook, a zip64, another compression, a document type, a
 * workbook with no worksheet).
 *
 * Run:  node tests/test_xlsx.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const zlib = require("zlib");

const DASH = path.join(__dirname, "..", "dashboard");
const DATASET = path.join(__dirname, "..", "pipeline", "out", "dataset-latest.json");

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail !== undefined ? "\n      " + JSON.stringify(detail) : ""}`); }
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const DB = {
  auth: {
    getSession: async () => ({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
  },
  from() { throw new Error("the workbook reader reaches no table"); },
  rpc() { throw new Error("the workbook reader calls no function"); },
};
const ctx = { console, URLSearchParams, setTimeout, Promise, TextDecoder, DecompressionStream, decodeURIComponent, encodeURIComponent };
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js", "_guild.js", "_comps.js", "_events.js", "_signup.js", "_history.js", "_import.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

/* the weapon catalog as build.py stamps it, for the detection */
const CATALOG = {};
for (const [key, w] of Object.entries(JSON.parse(fs.readFileSync(DATASET, "utf8")).weapons)) {
  CATALOG[key] = { name: w.display_name || key, role: null, item: "" };
  if (w.removed) CATALOG[key].removed = true;
}
const index = run("weaponIndex")(CATALOG, []);


/* ------------------------------------------------------- the zip writer */

const enc = new TextEncoder();

async function deflateRaw(bytes) {
  const stream = new CompressionStream("deflate-raw");
  const writer = stream.writable.getWriter();
  writer.write(bytes);
  writer.close();
  return new Uint8Array(await new Response(stream.readable).arrayBuffer());
}

/* entries: [{ name, data (text or bytes), method: 0 stored | 8 deflated,
   flags, crc, usize, csize (overrides for broken files) }] */
async function makeZip(entries, opts = {}) {
  const locals = [];
  const centrals = [];
  let offset = 0;
  for (const e of entries) {
    const name = enc.encode(e.name);
    const data = typeof e.data === "string" ? enc.encode(e.data) : e.data;
    const method = e.method == null ? 8 : e.method;
    const body = method === 8 ? await deflateRaw(data) : (e.raw || data);
    const crc = e.crc != null ? e.crc : zlib.crc32(data) >>> 0;
    const usize = e.usize != null ? e.usize : data.length;
    const csize = e.csize != null ? e.csize : body.length;
    const local = Buffer.alloc(30 + name.length);
    local.writeUInt32LE(0x04034b50, 0); local.writeUInt16LE(20, 4); local.writeUInt16LE(e.flags || 0, 6);
    local.writeUInt16LE(method, 8); local.writeUInt32LE(crc, 14); local.writeUInt32LE(csize, 18);
    local.writeUInt32LE(usize, 22); local.writeUInt16LE(name.length, 26); local.writeUInt16LE(0, 28);
    Buffer.from(name).copy(local, 30);
    const central = Buffer.alloc(46 + name.length);
    central.writeUInt32LE(0x02014b50, 0); central.writeUInt16LE(20, 4); central.writeUInt16LE(20, 6);
    central.writeUInt16LE(e.flags || 0, 8); central.writeUInt16LE(method, 10); central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(csize, 20); central.writeUInt32LE(usize, 24); central.writeUInt16LE(name.length, 28);
    central.writeUInt32LE(offset, 42);
    Buffer.from(name).copy(central, 46);
    locals.push(local, Buffer.from(body));
    centrals.push(central);
    offset += local.length + body.length;
  }
  const cd = Buffer.concat(centrals);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  const count = opts.count != null ? opts.count : entries.length;
  end.writeUInt16LE(count, 8); end.writeUInt16LE(count, 10);
  end.writeUInt32LE(cd.length, 12); end.writeUInt32LE(offset, 16);
  return new Uint8Array(Buffer.concat([...locals, cd, end]));
}


/* ------------------------------------------------------- the parts */

const NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
  + 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"';
const REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const PKG_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="${REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>`;

/* three sheets in tab order: Party (open when saved), a chart sheet, a hidden Gear */
const WORKBOOK = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook ${NS}><bookViews><workbookView activeTab="2"/></bookViews>
<sheets><sheet name="Gear &amp; food" sheetId="3" state="hidden" r:id="rId3"/><sheet name="Chart" sheetId="2" r:id="rId2"/>
<sheet name="Castle" sheetId="1" r:id="rId1"/></sheets></workbook>`;
const WORKBOOK_RELS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="${REL}/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="${REL}/chartsheet" Target="chartsheets/sheet1.xml"/>
<Relationship Id="rId3" Type="${REL}/worksheet" Target="/xl/worksheets/sheet2.xml"/>
<Relationship Id="rId4" Type="${REL}/sharedStrings" Target="sharedStrings.xml"/>
<Relationship Id="rId9" Type="${REL}/hyperlink" Target="https://example.com" TargetMode="External"/></Relationships>`;
/* 0 Weapon, 1 Player, 2 Role, 3 a rich string with a phonetic guide,
   4 a line break escaped, 5 entities, 6 Hallowfall, 7 Party 1, 8 Head */
const STRINGS = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<sst ${NS} count="9" uniqueCount="9"><si><t>Weapon</t></si><si><t>Player</t></si><si><t xml:space="preserve"> Role </t></si>
<si><r><rPr><b/></rPr><t>Heavy</t></r><r><t xml:space="preserve"> Mace</t></r><rPh sb="0" eb="1"><t>ignored</t></rPh></si>
<si><t>Disc_x000D_
Eff</t></si><si><t>Tom &amp; Jerry &lt;3 &#x41;&#66;</t></si><si><t>Hallowfall</t></si><si><t>Party 1</t></si><si><t>Head</t></si></sst>`;
/* the comp: a header in shared strings; a gap at column D (C stays
   empty and is kept); an inline string; numbers, a boolean, an error,
   formulas with and without a saved value; row 5 missing; a row with
   no references; a merge across A9:C9 */
const SHEET1 = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet ${NS}><dimension ref="A1:E10"/><sheetData>
<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c><c r="E1" t="s"><v>8</v></c></row>
<row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2" t="s"><v>4</v></c><c r="C2" t="inlineStr"><is><t>tank</t></is></c><c r="E2" t="inlineStr"><is><r><t>Guardian</t></r><r><t xml:space="preserve"> Helmet</t></r></is></c></row>
<row r="3"><c r="A3" t="s"><v>6</v></c><c r="B3" t="s"><v>5</v></c><c r="C3"><v>4.2999999999999998</v></c><c r="D3" t="b"><v>1</v></c><c r="E3" t="e"><v>#N/A</v></c></row>
<row r="4"><c r="A4" t="str"><f>CONCAT("Long","bow")</f><v>Longbow</v></c><c r="B4"><f>1+1</f></c><c r="C4"><v>1.0E-2</v></c></row>
<row r="6"><c r="A6" t="inlineStr"><is><t>Golem</t></is></c></row>
<row><c t="inlineStr"><is><t>Bedrock</t></is></c><c t="inlineStr"><is><t>Gus</t></is></c></row>
<row r="9"><c r="A9" t="s"><v>7</v></c><c r="B9" t="inlineStr"><is><t>stale</t></is></c><c r="C9" t="inlineStr"><is><t>stale</t></is></c></row>
<row r="10"><c r="A10" t="inlineStr"><is><t>Warbow</t></is></c><c r="B10"><v>3</v></c></row>
</sheetData><mergeCells count="1"><mergeCell ref="A9:C9"/></mergeCells></worksheet>`;
const SHEET2 = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<x:worksheet xmlns:x="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><x:sheetData>
<x:row r="1"><x:c r="A1" t="inlineStr"><x:is><x:t>Cleric Cowl</x:t></x:is></x:c></x:row></x:sheetData></x:worksheet>`;

const PARTS = [
  { name: "[Content_Types].xml", data: '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>', method: 0 },
  { name: "_rels/.rels", data: PKG_RELS, method: 8 },
  { name: "xl/workbook.xml", data: WORKBOOK, method: 8 },
  { name: "xl/_rels/workbook.xml.rels", data: WORKBOOK_RELS, method: 0 },
  { name: "xl/sharedStrings.xml", data: STRINGS, method: 8 },
  { name: "xl/worksheets/sheet1.xml", data: SHEET1, method: 8 },
  { name: "xl/worksheets/sheet2.xml", data: SHEET2, method: 0 },
  { name: "xl/chartsheets/sheet1.xml", data: "<chartsheet/>", method: 0 },
];

const refused = async (bytes, read) => {
  try { await (read ? read(bytes) : run("readWorkbook")(bytes)); return "read"; }
  catch (err) { return (err && err.code) || String(err); }
};


(async () => {

/* 1 - what a file is, and a text file's encoding */
{
  const kind = run("fileKind");
  check("a zip's signature is a workbook, an Office compound file's an older one, anything else text",
        kind(enc.encode("PK\x03\x04rest")) === "zip" && kind(new Uint8Array([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1, 0]))  === "cfb"
        && kind(enc.encode("Weapon,Player")) === "text" && kind(new Uint8Array(0)) === "text");
  const decode = run("decodeText");
  check("text: UTF-8 with or without its mark, UTF-16 by its mark, Windows-1252 where UTF-8 does not decode",
        decode(new Uint8Array([0xef, 0xbb, 0xbf, ...enc.encode("Café")])) === "Café" && decode(enc.encode("Café")) === "Café"
        && decode(new Uint8Array([0xff, 0xfe, 0x43, 0, 0x61, 0])) === "Ca" && decode(new Uint8Array([0x43, 0x61, 0x66, 0xe9])) === "Café");
}

/* 2 - the workbook: its sheets, its strings, its cells */
const book = await run("readWorkbook")(await makeZip(PARTS));
{
  check("the worksheets in tab order, a chart sheet left out, a hidden one marked, entities decoded",
        same(book.sheets.map(s => `${s.name}|${s.hidden}|${s.path}`), ["Gear & food|true|xl/worksheets/sheet2.xml", "Castle|false|xl/worksheets/sheet1.xml"]), book.sheets);
  check("the sheet open when the workbook was saved is read first (activeTab counts every sheet)", book.active === 1, book.active);
  check("shared strings: rich runs joined, the phonetic guide left out, an escaped line break, entities and character references",
        same(book.strings, ["Weapon", "Player", " Role ", "Heavy Mace", "Disc\r\nEff", "Tom & Jerry <3 AB", "Hallowfall", "Party 1", "Head"]), book.strings);

  const sheet = await run("readWorkbookSheet")(book, 1);
  check("the cells row by row: shared and inline strings, a number in its shortest form, TRUE, an error and an unvalued formula empty, a formula's saved text",
        same(sheet.cells[0], ["Weapon", "Player", "Role", "", "Head"]) && same(sheet.cells[1], ["Heavy Mace", "Disc\r\nEff", "tank", "", "Guardian Helmet"])
        && same(sheet.cells[2], ["Hallowfall", "Tom & Jerry <3 AB", "4.3", "TRUE"]) && same(sheet.cells[3], ["Longbow", "", "0.01"]), sheet.cells);
  check("a missing row is no row; a row and its cells without references follow the row before; the merge keeps its top-left cell, the stale cells read empty",
        same(sheet.cells.slice(4), [["Golem"], ["Bedrock", "Gus"], ["Party 1"], ["Warbow", "3"]]), sheet.cells.slice(4));
  check("the read says what it met: one merged range, one formula saved without a value, nothing cut, the sheet's name",
        sheet.merged === 1 && sheet.unvalued === 1 && sheet.cut === false && sheet.name === "Castle" && sheet.rows === sheet.cells.length, sheet);
  const hidden = await run("readWorkbookSheet")(book, 0);
  check("a stored part and prefixed element names read too", same(hidden.cells, [["Cleric Cowl"]]), hidden.cells);
  check("a sheet past the list is refused", await refused(null, () => run("readWorkbookSheet")(book, 5)) === "noSheet");
}

/* 3 - the same path a paste takes: the box's text reads back to the same cells, the detection to the same rows */
{
  const sheet = await run("readWorkbookSheet")(book, 1);
  const text = run("cellsText")(sheet.cells);
  const back = run("parseSheet")(text);
  check("the cells written as the paste box's tab-separated text read back to the same cells (a line break inside a cell quoted)",
        back.delimiter === "\t" && same(back.cells, sheet.cells), { text, cells: back.cells });
  const one = [["Longbow, Disc"], ["Warbow; Eff"], ["Hallowfall | Gus"], ['"Witchwork" (DPS)']];
  const backOne = run("parseSheet")(run("cellsText")(one));
  check("one column of cells with commas, semicolons, pipes and quotes reads back whole", same(backOne.cells, one), backOne.cells);
  const detect = run("detectColumns"), sheetRows = run("sheetRows");
  const fromBook = sheetRows(sheet.cells, detect(sheet.cells, index), index);
  const fromPaste = sheetRows(back.cells, detect(back.cells, index), index);
  check("the workbook's cells and their paste give the same columns and rows",
        same(detect(sheet.cells, index), detect(back.cells, index)) && same(fromBook, fromPaste) && fromBook.length > 0
        && fromBook.some(r => r.text === "Heavy Mace" && r.match.key === "2H_MACE") && fromBook.some(r => r.text === "Hallowfall" && r.match.status === "exact"),
        fromBook.map(r => `${r.text}:${r.match.status}`));
}

/* 4 - the bounds */
{
  const rowsMax = run("IMPORT_ROWS_MAX"), colsMax = run("IMPORT_COLUMNS_MAX");
  const many = Array.from({ length: rowsMax + 100 }, (_, i) => `<row r="${i + 1}"><c r="A${i + 1}" t="inlineStr"><is><t>Longbow ${i}</t></is></c></row>`).join("");
  const big = run("sheetGrid")(`<worksheet><sheetData>${many}</sheetData></worksheet>`, []);
  check("at most IMPORT_ROWS_MAX rows with a value are read, and the read says it was cut", big.cells.length === rowsMax && big.cut);
  const wide = run("sheetGrid")(`<worksheet><sheetData><row r="1"><c r="A1"><v>1</v></c><c r="XFD1"><v>2</v></c></row></sheetData></worksheet>`, []);
  check("a cell past IMPORT_COLUMNS_MAX is dropped and the read says so; the far column never widens the row",
        same(wide.cells, [["1"]]) && wide.cut && colsMax === 64);
  const long = run("sheetGrid")(`<worksheet><sheetData>${Array.from({ length: 30 }, (_, i) => `<row r="${i + 1}"><c r="A${i + 1}" t="inlineStr"><is><t>${"x".repeat(9000)}</t></is></c></row>`).join("")}</sheetData></worksheet>`, []);
  check("at most IMPORT_TEXT_MAX characters are read", long.cut && long.cells.length * 9000 <= run("IMPORT_TEXT_MAX"));
  check("a file past IMPORT_FILE_MAX is refused before it is opened",
        await refused(new Uint8Array(run("IMPORT_FILE_MAX") + 1).fill(0x50, 0, 1).fill(0x4b, 1, 2).fill(3, 2, 3).fill(4, 3, 4)) === "fileTooBig");
  check("a directory listing more than XLSX_ENTRIES_MAX entries is refused",
        await refused(await makeZip(PARTS, { count: run("XLSX_ENTRIES_MAX") + 1 })) === "xlsxTooBig");
  const zeros = new Uint8Array(run("XLSX_PART_MAX") + 1024);
  const bomb = PARTS.map(p => (p.name === "xl/sharedStrings.xml" ? { name: p.name, data: zeros, method: 8, usize: 100 } : p));
  check("a part that inflates past XLSX_PART_MAX whatever size it declares is refused (the shared strings)",
        await refused(await makeZip(bomb)) === "xlsxTooBig");
  const pad = enc.encode(SHEET1.replace("</sheetData>", "</sheetData>" + "<!-- pad -->".repeat(Math.ceil(run("XLSX_PART_MAX") / 12))));
  const cutBook = await run("readWorkbook")(await makeZip(PARTS.map(p => (p.name === "xl/worksheets/sheet1.xml" ? { name: p.name, data: pad, method: 8 } : p))));
  const cutSheet = await run("readWorkbookSheet")(cutBook, 1);
  check("a sheet past XLSX_PART_MAX is read up to it, its cells kept and the read marked cut",
        cutSheet.cut && same(cutSheet.cells[0], ["Weapon", "Player", "Role", "", "Head"]), { cut: cutSheet.cut, first: cutSheet.cells[0] });
}

/* 5 - refused, with the way round */
{
  const good = await makeZip(PARTS);
  check("a damaged zip (cut short, no end record) is refused as damaged", await refused(good.slice(0, good.length - 30)) === "xlsxCorrupt");
  const badCrc = await makeZip(PARTS.map(p => (p.name === "xl/_rels/workbook.xml.rels" ? Object.assign({}, p, { crc: 12345 }) : p)));
  check("an entry whose CRC-32 does not match its bytes is refused as damaged", await refused(badCrc) === "xlsxCorrupt");
  const badDeflate = await makeZip(PARTS.map(p => (p.name === "xl/workbook.xml" ? { name: p.name, data: enc.encode(WORKBOOK), method: 8, csize: 8 } : p)));
  const badDeflateRead = await refused(badDeflate);
  check("deflated bytes that do not inflate are refused as damaged", badDeflateRead === "xlsxCorrupt", badDeflateRead);
  const locked = new Uint8Array(4096);
  locked.set([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]);
  locked.set([..."EncryptedPackage"].flatMap(ch => [ch.charCodeAt(0), 0]), 1200);
  const xls = new Uint8Array(4096);
  xls.set([0xd0, 0xcf, 0x11, 0xe0, 0xa1, 0xb1, 0x1a, 0xe1]);
  check("a workbook protected by a password (its package encrypted inside a compound file) is refused as locked; an .xls as an .xls",
        await refused(locked) === "xlsxLocked" && await refused(xls) === "xls");
  const flagged = await makeZip(PARTS.map(p => (p.name === "xl/workbook.xml" ? Object.assign({}, p, { flags: 1 }) : p)));
  check("a zip entry encrypted by the zip itself is refused as locked", await refused(flagged) === "xlsxLocked");
  const ods = await makeZip([{ name: "mimetype", data: "application/vnd.oasis.opendocument.spreadsheet", method: 0 }, { name: "content.xml", data: "<office:document-content/>", method: 8 }]);
  const xlsb = await makeZip([{ name: "xl/workbook.bin", data: "binary", method: 0 }]);
  check("a zip that is no workbook (an .ods, an .xlsb) is refused with the way round", await refused(ods) === "notWorkbook" && await refused(xlsb) === "notWorkbook");
  check("text named as a workbook is no workbook", await refused(enc.encode("Weapon,Player\nLongbow,Disc")) === "notWorkbook");
  check("a zip64 directory is refused as stored in a way the page does not read", await refused(await makeZip(PARTS, { count: 0xffff })) === "xlsxUnsupported");
  const lzma = await makeZip(PARTS.map(p => (p.name === "xl/workbook.xml" ? { name: p.name, data: WORKBOOK, method: 14, raw: enc.encode(WORKBOOK) } : p)));
  check("a compression other than stored and deflate is refused the same way", await refused(lzma) === "xlsxUnsupported");
  const doctype = await makeZip(PARTS.map(p => (p.name === "xl/workbook.xml" ? { name: p.name, data: '<!DOCTYPE x [<!ENTITY a "aaaa">]>' + WORKBOOK.replace(/^<\?xml[^>]*\?>/, ""), method: 8 } : p)));
  check("a part carrying a document type is refused, its entities never expanded", await refused(doctype) === "xlsxUnsupported");
  const charts = await makeZip(PARTS.map(p => (p.name === "xl/workbook.xml"
    ? { name: p.name, data: `<workbook ${NS}><sheets><sheet name="Chart" sheetId="2" r:id="rId2"/></sheets></workbook>`, method: 8 } : p)));
  check("a workbook with no worksheet is refused", await refused(charts) === "noSheet");
  const noRoot = await makeZip(PARTS.map(p => (p.name === "xl/workbook.xml" ? { name: p.name, data: "<notes/>", method: 8 } : p)));
  check("a workbook part that is no workbook is refused as damaged", await refused(noRoot) === "xlsxCorrupt");
  const M = run("IMPORT_MSG");
  check("every refusal has its sentence, and each names the way round or the bound",
        ["xlsxCorrupt", "xlsxLocked", "xls", "notWorkbook", "xlsxUnsupported", "xlsxTooBig", "fileTooBig", "noInflate", "noSheet", "sheetEmpty"]
          .every(k => typeof M[k] === "string" && M[k].length > 20)
        && /paste/.test(M.xlsxCorrupt) && /password/.test(M.xlsxLocked) && /\.xlsx or CSV/.test(M.xls)
        && M.xlsxTooBig.includes(String(run("XLSX_ENTRIES_MAX"))) && M.fileTooBig.includes("20 MB"));
  const msg = run("importErrorMessage");
  check("a refusal reads as its sentence through the import's wording", msg(run("importError")("xlsxLocked")) === M.xlsxLocked);
}

/* 6 - the walk itself */
{
  const seen = [];
  run("xmlWalk")('<?xml version="1.0"?><!-- a comment --><a:b x="1 > 0" y=\'q\'><c/>t &amp; u<![CDATA[<raw>]]></a:b>', {
    open(name, attrs) { seen.push(`open:${name}:${JSON.stringify(attrs)}`); },
    close(name) { seen.push(`close:${name}`); },
    text(t) { if (t.trim()) seen.push(`text:${t}`); }
  });
  check("the walk: a prefix dropped, a quoted > kept inside its value, an empty element opened and closed, text and CDATA decoded as written",
        same(seen, ['open:b:{"x":"1 > 0","y":"q"}', "open:c:{}", "close:c", "text:t & u", "text:<raw>", "close:b"]), seen);
  const partial = [];
  run("xmlWalk")('<row r="1"><c r="A1"><v>1</v></c><c r="B1"><v>2', { open(name) { partial.push(name); } });
  check("a part cut short ends at its last whole tag", same(partial, ["row", "c", "v", "c", "v"]), partial);
  check("cell references read as row and column from zero", same(run("cellRef")("B3"), { row: 2, col: 1 }) && same(run("cellRef")("XFD1"), { row: 0, col: 16383 }) && run("cellRef")("3B") === null);
  check("a relationship's target resolves from its part's folder or the package's root",
        run("partPath")("xl/", "worksheets/sheet1.xml") === "xl/worksheets/sheet1.xml" && run("partPath")("xl/", "/xl/s.xml") === "xl/s.xml"
        && run("partPath")("xl/worksheets/", "../sharedStrings.xml") === "xl/sharedStrings.xml");
}

/* 7 - the package names the workbook part */
{
  const moved = PARTS.map(p => {
    if (p.name === "_rels/.rels") return { name: p.name, data: PKG_RELS.replace("xl/workbook.xml", "xl/book.xml"), method: 8 };
    if (p.name === "xl/workbook.xml") return { name: "xl/book.xml", data: WORKBOOK, method: 8 };
    if (p.name === "xl/_rels/workbook.xml.rels") return { name: "xl/_rels/book.xml.rels", data: WORKBOOK_RELS, method: 0 };
    return p;
  });
  const b = await run("readWorkbook")(await makeZip(moved));
  check("the workbook part is the one the package's relationships name", b.sheets.length === 2 && b.sheets[1].name === "Castle");
  const cased = await run("readWorkbook")(await makeZip(PARTS.map(p => (p.name === "xl/worksheets/sheet1.xml" ? Object.assign({}, p, { name: "xl/Worksheets/Sheet1.xml" }) : p))));
  check("a part's name is read whatever its case", same((await run("readWorkbookSheet")(cased, 1)).cells[0], ["Weapon", "Player", "Role", "", "Head"]));
}

/* 8 - the module stays inside its boundary */
{
  const src = fs.readFileSync(path.join(DASH, "_import.js"), "utf8");
  check("the reader is the page's own: DecompressionStream for deflate, no zip or spreadsheet library",
        /new DecompressionStream\("deflate-raw"\)/.test(src) && !/JSZip|SheetJS|\bXLSX\.|\bimport\(|createElement\("script"\)/.test(src));
}

console.log(`\n${pass}/${pass + fail} workbook reader tests passed`);
process.exit(fail ? 1 : 0);
})();
