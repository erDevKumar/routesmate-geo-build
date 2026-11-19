#!/usr/bin/env python3
"""Reads OSM XML of candidate ways (with node locations: osmium add-locations-to-ways | osmium cat -f osm)
on stdin, writes an .osc adding the overlay's access tags (config/vehicle_overlay.json).
Usage: ... | apply_overlay.py [--status confirmed,user-approved-2026-11-19] > overlay.osc"""
import json, re, sys, xml.etree.ElementTree as ET
from pathlib import Path

CFG = Path(__file__).resolve().parent.parent / "config" / "vehicle_overlay.json"
DEFAULT_STATUSES = {"confirmed", "user-approved-2026-11-19"}


def in_bbox(way, bbox):
    w, s, e, n = bbox
    for nd in way.findall("nd"):
        if nd.get("lat") is not None and w <= float(nd.get("lon")) <= e and s <= float(nd.get("lat")) <= n:
            return True
    return False


MOTORWAY = ("motorway", "motorway_link")
LINK_HOPS = 6  # ways from a named-rule way; measured 2026-11-19 north zone: 3 leaves a KMP/DME interchange ramp, 6 to 10 add no more ways from there


def link_ways(ways, caught, seeds):
    """Unnamed ramps/splits/bridges of a barred expressway. ways: {id: (tags, nodes)}; caught: {id: rule}.
    A way qualifies if it is highway=motorway/_link with no name and no ref, within LINK_HOPS shared-node hops of a
    caught way through such ways, and its whole connected unnamed-motorway component touches no motorway-class way
    outside the barred set (a ramp joining a legal expressway, e.g. Noida-Greater Noida, stays open).
    Returns {way_id: rule}."""
    bare = {i for i, (t, _) in ways.items() if t.get("highway") in MOTORWAY and not any(t.get(k) for k in ("name", "ref", "alt_name", "int_ref", "official_name"))}
    at = {}
    for i, (t, nds) in ways.items():
        if i in bare or i in caught or t.get("highway") in MOTORWAY:
            for n in nds:
                at.setdefault(n, []).append(i)
    nbrs = lambda i: {j for n in ways[i][1] for j in at.get(n, ()) if j != i}
    comp_of, comps = {}, []
    for i in bare:
        if i in comp_of or i in caught:
            continue
        c, stack = set(), [i]
        while stack:
            k = stack.pop()
            if k in c:
                continue
            c.add(k)
            stack += [j for j in nbrs(k) if j in bare and j not in caught and j not in c]
        for k in c:
            comp_of[k] = len(comps)
        comps.append(c)
    # a component is clean when every motorway-class neighbour is barred or inside it
    clean = [all(j in c or j in caught for k in c for j in nbrs(k)) for c in comps]
    out, frontier = {}, {i: caught[i] for i in seeds}
    for _ in range(LINK_HOPS):
        nxt = {}
        for i, rule in frontier.items():
            for j in nbrs(i):
                if j in comp_of and clean[comp_of[j]] and j not in out and j not in caught:
                    nxt[j] = rule
        out.update(nxt)
        frontier = nxt
    return out


def overlay(root, cfg, statuses):
    rules = [(re.compile(r["name"]), r) for r in cfg["rules"] if r["status"] in statuses]
    byid = {r["id"]: r for _, r in rules}
    mod = ET.Element("modify")
    hits, ways, caught, elems = {}, {}, {}, {}
    for way in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in way.findall("tag")}
        wid = way.get("id")
        elems[wid] = way
        ways[wid] = (tags, [nd.get("ref") for nd in way.findall("nd")])
        for rx, r in rules:
            if tags.get("highway") not in r.get("highways", cfg["highways"]):
                continue
            if not any(rx.search(tags.get(k, "")) for k in ("name", "ref")):
                continue
            if "bbox" in r and not in_bbox(way, r["bbox"]):
                continue
            caught[wid] = r["id"]
            break
    # city rules (bbox) get no link propagation: only the access-controlled expressway rules do
    linked = link_ways(ways, caught, {w for w, rid in caught.items() if "bbox" not in byid[rid]})
    for wid, rid in {**caught, **linked}.items():
        way, tags, r = elems[wid], ways[wid][0], byid[rid]
        add = {k: v for k, v in r["tags"].items() if k not in tags}
        if add:
            for k, v in add.items():
                ET.SubElement(way, "tag", k=k, v=v)
            mod.append(way)
            key = rid + ("+links" if wid in linked else "")
            hits[key] = hits.get(key, 0) + 1
    osc = ET.Element("osmChange", version="0.6", generator="routesmate-overlay")
    osc.append(mod)
    return osc, hits


def main():
    statuses = DEFAULT_STATUSES
    if "--status" in sys.argv:
        statuses = set(sys.argv[sys.argv.index("--status") + 1].split(","))
    cfg = json.loads(CFG.read_text())
    osc, hits = overlay(ET.parse(sys.stdin).getroot(), cfg, statuses)
    ET.ElementTree(osc).write(sys.stdout.buffer, encoding="utf-8", xml_declaration=True)
    print("overlay hits:", hits, file=sys.stderr)


if __name__ == "__main__":
    main()
