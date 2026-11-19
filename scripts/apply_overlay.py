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


def overlay(root, cfg, statuses):
    rules = [(re.compile(r["name"]), r) for r in cfg["rules"] if r["status"] in statuses]
    mod = ET.Element("modify")
    hits = {}
    for way in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in way.findall("tag")}
        for rx, r in rules:
            if tags.get("highway") not in r.get("highways", cfg["highways"]):
                continue
            if not any(rx.search(tags.get(k, "")) for k in ("name", "ref")):
                continue
            if "bbox" in r and not in_bbox(way, r["bbox"]):
                continue
            add = {k: v for k, v in r["tags"].items() if k not in tags}
            if add:
                for k, v in add.items():
                    ET.SubElement(way, "tag", k=k, v=v)
                mod.append(way)
                hits[r["id"]] = hits.get(r["id"], 0) + 1
            break
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
