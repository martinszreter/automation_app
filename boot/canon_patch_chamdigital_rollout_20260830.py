"""One-off canon migration: add the 4.1 ChamDigital market census + DACH rollout thesis.

Run by the portfolio Railway service with CANON_RW_URL in its environment.
Idempotent: all three mutations have durable markers. Implements the canon
read -> insert -> re-read -> duplicate-version recovery -> prune-to-3 protocol.
"""
from __future__ import annotations

import json
import os
import urllib.request

CANON_URL = os.environ["CANON_RW_URL"]
BUS_URL = "https://startend.app.n8n.cloud/webhook/agent-report-7q3v9x2k"
WHO = "HQ_GPT"
TIMEOUT = 30

DECISION = """2026-08-30 | 4.1 SERVICES | DECISION | CHAMDIGITAL ROLLOUT THESIS LOCKED. Switzerland is the proving market, not the final market. Finish the current product-quality/checkout gate first; no expansion work may distract CLAIM 38. After the product is sellable, prove the motion in German-speaking Switzerland with preview-before-purchase, manual individual outreach, real delivery, reviews and case studies. Expansion gate = 10 paying D-CH customers plus repeatable delivery and credible customer proof. Then test Austria as the international replication lab; then Germany region-by-region and vertical-by-vertical (Bavaria -> Baden-Württemberg before nationwide), reusing the same site-engine rather than building country-specific products. Germany scales through winning vertical factories (specialty retail, hair/beauty, finishing trades, food retail, garages, then adjacent winners), not a generic 'websites for every SME' pitch. Long-term product identity = AI-powered SME digital-upgrade factory: prospect scoring -> observed web problem -> personalised before/after preview -> localised offer -> checkout -> editor/domain migration -> production site. The moat is the preview-before-purchase system, vertical templates, local trust, delivery data, reviews and migration expertise; the lead list alone is not a moat. Country acquisition must be local-law specific: no automated cold outreach. Austria is consent-first for promotional calls/e-mail/SMS under TKG guidance; Germany UWG §7 requires prior express consent for electronic mail and at least presumed consent for B2B promotional calls. Same core technology, different brand/trust/pricing/distribution by market."""

INITIATIVE_APPEND = """ 30 AUG 2026 MARKET/ROLLOUT THESIS (HQ_GPT + Grok census, founder agreed): official Swiss ceiling = 649,353 enterprises (BFS STATENT 2024); 636,020 are 1-49 employee institutional units (owner-led proxy, inference). Core ChamDigital-shaped sectors F/G/I/L/M/Q/R/S contain ~487,928 establishments (inference). Working HIGH-PRIORITY pool is a MODEL, not an official statistic: 12k conservative / 28k base / 55k aggressive. Grok verified 84 real prospects honestly (65 HOT / 19 WARM), short of the requested 100. First wedge: Cham -> Ennetsee -> Baar -> street-level Zug -> Schwyz/Luzern; first verticals = specialty retail, hair/beauty, finishing trades, bakery/butcher, independent garages. 30/60/90 moat: 20-50 personalised previews + 1-3 paid; then 3 vertical templates + before/after proof + reviews/domain-migration story; then 10 paying D-CH customers. AFTER that: Austria replication test, then Germany Bavaria -> Baden-Württemberg -> national by winning verticals. Long-term identity = AI SME digital-upgrade factory; same site-engine, market-specific brand/trust/pricing/lawful acquisition. No automated cold outreach; research automation is separate from contact."""

BOARD_SECTION = r'''
<!-- HQ_GPT_CHAMDIGITAL_ROLLOUT_20260830 -->
<h2><span class="k">4.1 SERVICES · CHAMDIGITAL</span>From Swiss website shop to DACH digital-upgrade factory</h2>

<div class="dark" style="margin-top:8px">
  <div class="label" style="color:#9A968D;margin-bottom:10px">THE LONG-TERM THESIS — LOCKED 30 AUG 2026</div>
  <div class="display" style="font-size:32px;line-height:1.05;color:#fff;max-width:980px">CH proves the machine. AT proves replication. DE scales the winning verticals.</div>
  <div style="font-size:14px;line-height:1.65;color:#D5D1C9;max-width:1100px;margin-top:12px">
    ChamDigital is not meant to end as a small web agency. The target is one <b style="color:#fff">AI-powered SME digital-upgrade factory</b>:
    find an operating business → diagnose the visible web/domain/conversion problem → generate a personalised before/after preview →
    localise the offer → checkout → customer editor/domain migration → production site. The same <code>martinszreter/site-engine</code>
    stays underneath; country and vertical become data/config, not new product code.
  </div>
</div>

<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:10px">
  <div class="card" style="flex:1 1 220px;border-left-color:#DA291C">
    <div class="label">SWISS FACT · BFS 2024</div>
    <div class="display" style="font-size:30px">649,353</div>
    <div style="font-size:12px;line-height:1.45">enterprises / institutional units. <b>636,020</b> are in the 1–49 employee proxy (inference from BFS size classes).</div>
  </div>
  <div class="card" style="flex:1 1 220px;border-left-color:#DA291C">
    <div class="label">ICP-SHAPED CEILING</div>
    <div class="display" style="font-size:30px">~487,928</div>
    <div style="font-size:12px;line-height:1.45">establishments across construction, trade, hospitality, real estate, professional, health, recreation and other services. This is a ceiling, not a prospect count.</div>
  </div>
  <div class="card" style="flex:1 1 220px;border-left-color:#DA291C">
    <div class="label">WORKING HIGH-PRIORITY MODEL</div>
    <div class="display" style="font-size:30px">12k · 28k · 55k</div>
    <div style="font-size:12px;line-height:1.45">conservative · base · aggressive. <b>MODEL / INFERENCE, not an official census statistic.</b> It must be validated by conversion data.</div>
  </div>
  <div class="card" style="flex:1 1 220px;border-left-color:#DA291C">
    <div class="label">REAL SAMPLE CHECK</div>
    <div class="display" style="font-size:30px">84 verified</div>
    <div style="font-size:12px;line-height:1.45"><b>65 HOT · 19 WARM.</b> Grok stopped honestly below the requested 100 instead of manufacturing rows. ZG supplied 27 of the confirmed sample.</div>
  </div>
</div>

<div class="scroll" style="margin-top:10px"><table style="min-width:940px">
  <tr><th>STAGE</th><th>MARKET</th><th>WHAT WE PROVE</th><th>ACQUISITION / PRODUCT RULE</th><th>GATE TO NEXT STAGE</th></tr>
  <tr>
    <td><b>1 · NOW</b></td>
    <td><b>🇨🇭 German-speaking Switzerland</b><br>Cham → Ennetsee → Baar → Zug → Schwyz/Luzern</td>
    <td>Product quality, instant personalised previews, checkout, delivery, review loop and real willingness to pay.</td>
    <td>Research can be automated. Contact remains <b>manual, individual and genuinely personalised</b>. Do not unlock distribution before the current 4.1 quality/checkout gate.</td>
    <td><b>10 paying D-CH customers</b> + repeatable delivery + credible reviews/case studies.</td>
  </tr>
  <tr>
    <td><b>2 · REPLICATION</b></td>
    <td><b>🇦🇹 Austria</b><br>same winning verticals first</td>
    <td>Whether the Swiss factory travels when price, brand, trust signals and distribution are localised.</td>
    <td>Do <b>not</b> copy the Swiss outreach motion. Austria's current TKG guidance is consent-first for promotional calls, e-mail and SMS, with narrow existing-customer exceptions. Use lawful inbound/partnership/postal/other tested channels.</td>
    <td>International unit economics and one repeatable Austrian acquisition channel proven before broader scaling.</td>
  </tr>
  <tr>
    <td><b>3 · SCALE</b></td>
    <td><b>🇩🇪 Germany</b><br>Bavaria → Baden-Württemberg → nationwide</td>
    <td>Industrial scale by vertical, not a vague nationwide SME offer. One factory for roofers/trades, one for salons, one for garages, etc. — all configurations on the same engine.</td>
    <td>Germany UWG §7: electronic-mail advertising generally needs prior express consent; B2B promotional calls need at least presumed consent. Build legal acquisition around each winning vertical instead of mass cold e-mail.</td>
    <td>Expand region/vertical only when the preceding cell has positive paid conversion and delivery economics.</td>
  </tr>
</table></div>

<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:10px">
  <div class="card" style="flex:1 1 300px">
    <b>FIRST VERTICALS — IN ORDER</b><br>
    <span style="font-size:12.5px;line-height:1.6">1 specialty retail · 2 hair/barber/beauty · 3 finishing trades (electrician/plumber/painter/carpenter/HVAC) · 4 bakery/butcher/local food · 5 independent garage/tyre/detailing. Then fitness/yoga, physio/therapy, gastro and other winners only when evidence beats the first five.</span>
  </div>
  <div class="card" style="flex:1 1 300px">
    <b>30 / 60 / 90-DAY MOAT AFTER PRODUCT GATE</b><br>
    <span style="font-size:12.5px;line-height:1.6"><b>30:</b> 20–50 Cham/Ennetsee personalised previews, target 1–3 paid founders. <b>60:</b> three vertical templates, public before/after proof, reviews, domain-migration story. <b>90:</b> 10 paying D-CH customers; only then activate the Austria replication work.</span>
  </div>
  <div class="card" style="flex:1 1 300px">
    <b>THE MOAT IS NOT THE LIST</b><br>
    <span style="font-size:12.5px;line-height:1.6">A competitor can buy or crawl a prospect list. The defence is <b>preview-before-purchase + vertical templates + local trust + fast domain migration + customer proof + accumulated delivery/conversion data</b>. The census says there is enough inventory; execution and conversion are the scarce resources.</span>
  </div>
</div>

<div class="card" style="margin-top:10px;border-left-color:#DA291C;background:#fff3f3">
  <b>MARKET SCALE BEYOND CH — context, not permission to expand now.</b>
  Austria's official 2024 census reports <b>744,851 enterprises</b>, including <b>459,029 one-person enterprises</b>.
  Germany's Destatis SME statistics report about <b>3.2 million SMEs</b> in the covered 2023 sectors, including about <b>2.6 million micro-enterprises</b>.
  These numbers make DACH enormous; they do <b>not</b> change the current priority: 4.1 quality → checkout → paid Swiss proof first.
</div>

<div style="font-size:11px;color:#666;margin:9px 0 20px;line-height:1.5">
  <b>Evidence / definitions:</b> Swiss counts: BFS STATENT 2024, data stand 20 Aug 2026. Website-presence context: localsearch/HSLU KMU Digital Pulse 2025 (its directory universe is not the BFS universe; never multiply the two and call the result a fact).
  Austria: Statistik Austria Census of Local Units of Employment 2024. Germany: Destatis SME statistics, reference year 2023. Outreach rules: WKO TKG guidance updated 15 Aug 2026; Germany UWG §7.
  Grok prospect sample checked 30 Aug 2026. Working 12k/28k/55k high-priority pool is explicitly an internal model.
</div>
'''


def request(payload: dict) -> object:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(CANON_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


def rows(key: str) -> list[dict]:
    value = request({"action": "read", "keyValue": key})
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"STOP: canon read returned no rows for {key}")
    return [r for r in value if isinstance(r, dict)]


def version(row: dict) -> int:
    return int(row.get("version", 0))


def newest(key: str) -> dict:
    return max(rows(key), key=version)


def delete_row(row_id: object) -> None:
    if row_id is not None:
        request({"action": "delete", "id": row_id})


def insert(key: str, ver: int, content: str, note: str) -> None:
    request({"action": "insert", "file": key, "version": ver, "content": content, "note": note, "updated_by": WHO})


def prune(key: str) -> None:
    current = sorted(rows(key), key=lambda r: (version(r), int(r.get("id", 0) or 0)), reverse=True)
    for old in current[3:]:
        delete_row(old.get("id"))
    print("PRUNE", key, "kept", [(r.get("version"), r.get("id")) for r in current[:3]])


def mutate(key: str, marker: str, transform, note: str) -> int:
    # Mandatory immediate re-read before writing.
    before_rows = rows(key)
    base = max(before_rows, key=version)
    base_content = str(base.get("content", ""))
    if marker in base_content:
        print("SKIP", key, "marker already canonical at v", version(base))
        prune(key)
        return version(base)

    target_version = max(version(r) for r in before_rows) + 1
    new_content = transform(base_content)
    insert(key, target_version, new_content, note)

    # Mandatory immediate re-read after writing.
    after_rows = rows(key)
    at_target = [r for r in after_rows if version(r) == target_version]
    if len(at_target) > 1:
        print("RACE", key, "duplicate version", target_version, "rows", [r.get("id") for r in at_target])
        ours = [r for r in at_target if r.get("updated_by") == WHO and marker in str(r.get("content", ""))]
        others = [r for r in at_target if r not in ours]
        merge_base = max(others or at_target, key=lambda r: int(r.get("id", 0) or 0))
        merged = transform(str(merge_base.get("content", "")))
        next_version = max(version(r) for r in after_rows) + 1
        insert(key, next_version, merged, note + " | race re-merge")
        reread = rows(key)
        if marker not in str(max(reread, key=version).get("content", "")):
            raise RuntimeError(f"race recovery failed for {key}")
        for orphan in ours:
            delete_row(orphan.get("id"))
        target_version = next_version
    else:
        canonical = max(after_rows, key=version)
        if version(canonical) != target_version or marker not in str(canonical.get("content", "")):
            raise RuntimeError(f"post-write verification failed for {key}")

    prune(key)
    final = newest(key)
    print("WRITE_OK", key, "v", final.get("version"), "id", final.get("id"), "len", len(str(final.get("content", ""))))
    return version(final)


def transform_decisions(content: str) -> str:
    return DECISION + "\n\nupdated_by=HQ_GPT\n\n-----\n" + content


def transform_initiatives(content: str) -> str:
    marker = "30 AUG 2026 MARKET/ROLLOUT THESIS"
    if marker in content:
        return content
    start = content.find("| 4.1 | Swiss Websites (")
    if start < 0:
        raise RuntimeError("4.1 Swiss Websites row not found")
    end = content.find("\n", start)
    if end < 0:
        end = len(content)
    row = content[start:end].rstrip()
    if not row.endswith("|"):
        raise RuntimeError("4.1 row does not end with markdown pipe")
    patched = row[:-1] + INITIATIVE_APPEND + " |"
    return content[:start] + patched + content[end:]


def transform_board(content: str) -> str:
    if "HQ_GPT_CHAMDIGITAL_ROLLOUT_20260830" in content:
        return content
    anchor = '<h2><span class="k">Six pillars, six pages (_PROTOCOL)</span>Views registry</h2>'
    if anchor not in content:
        raise RuntimeError("BOARD_HTML insertion anchor not found")
    return content.replace(anchor, BOARD_SECTION + "\n" + anchor, 1)


def report_done(versions: dict[str, int]) -> None:
    try:
        with urllib.request.urlopen(BUS_URL, timeout=TIMEOUT) as response:
            state = json.loads(response.read().decode("utf-8"))
        cursor = state.get("bus_cursor") if isinstance(state, dict) else None
        if not cursor:
            print("BUS_WARN no cursor")
            return
        payload = {
            "team": "HQ_GPT",
            "project": "4.1 ChamDigital",
            "type": "DONE",
            "what": "Consolidated Grok Swiss census + CH→AT→DE rollout thesis into 4.1 initiative, 03_DECISIONS and lower HQ portfolio detail section.",
            "next": "Finish Claim 38 product-quality/checkout gate; then build the first 20–50 Cham/Ennetsee personalised previews.",
            "link": "https://portfolio-production-f01d.up.railway.app/ptf-k4x9m2.html",
            "bus_cursor": cursor,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(BUS_URL, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            print("BUS_DONE", response.status, response.read().decode("utf-8")[:500])
    except Exception as exc:
        print("BUS_WARN", repr(exc))


def main() -> None:
    versions = {}
    versions["00_INITIATIVES"] = mutate(
        "00_INITIATIVES",
        "30 AUG 2026 MARKET/ROLLOUT THESIS",
        transform_initiatives,
        "4.1 ChamDigital: consolidate Swiss census, first verticals and CH→AT→DE rollout thesis",
    )
    versions["03_DECISIONS"] = mutate(
        "03_DECISIONS",
        "CHAMDIGITAL ROLLOUT THESIS LOCKED",
        transform_decisions,
        "Lock 4.1 ChamDigital Switzerland→Austria→Germany rollout and acquisition doctrine",
    )
    versions["BOARD_HTML"] = mutate(
        "BOARD_HTML",
        "HQ_GPT_CHAMDIGITAL_ROLLOUT_20260830",
        transform_board,
        "Add lower 4.1 ChamDigital market census + DACH rollout detail section",
    )
    report_done(versions)
    print("DONE", versions)


if __name__ == "__main__":
    main()
