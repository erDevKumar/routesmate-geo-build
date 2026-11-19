import json, unittest, xml.etree.ElementTree as ET
from apply_overlay import overlay, CFG

def way(i, loc=(0, 0), **t):
    return f'<way id="{i}"><nd ref="1" lat="{loc[0]}" lon="{loc[1]}"/>' + "".join(f'<tag k="{k}" v="{v}"/>' for k, v in t.items()) + "</way>"

XML = "<osm>" + way(1, highway="motorway", name="Dwarka Expressway") \
    + way(2, highway="motorway", name="Dwarka Expressway", motorcycle="yes") \
    + way(3, highway="trunk", name="Dwarka Expressway") \
    + way(4, highway="motorway", name="Noida-Greater Noida Expressway") \
    + way(5, highway="motorway", name="Yamuna Expressway") \
    + way(6, (19.0, 72.85), highway="trunk", name="Eastern Freeway") \
    + way(7, (28.6, 77.2), highway="trunk", name="Eastern Freeway") \
    + way(8, (19.0, 72.85), highway="trunk", name="Western Express Highway") \
    + way(9, highway="motorway", name="DND Flyway", ref="DND") \
    + way(10, highway="motorway", ref="NH148NA") \
    + way(11, highway="motorway", name="Mumbai - Vadodara Expressway", ref="NE4") \
    + way(12, highway="motorway", name="Delhi - Vadodara Expressway", ref="NE-4") \
    + way(13, highway="motorway", name="Samruddhi Mahamarg", ref="ME-2") \
    + way(14, highway="motorway", name="Ahmedabad–Dholera Expressway", ref="NE8") \
    + way(15, highway="motorway", name="Trans Haryana Expressway", ref="NH152D") \
    + way(16, highway="trunk", name="Delhi - Amritsar - Katra Expressway") \
    + way(17, highway="motorway", name="Jaipur - Bandikui Expressway", motorcycle="yes") \
    + way(18, highway="motorway", name="Amritsar–Jamnagar Expressway") \
    + way(19, highway="motorway", name="Jind - Gohana - Sonipat Expressway") \
    + way(20, highway="motorway", name="Grand Trunk Road", ref="NH44") + "</osm>"

class T(unittest.TestCase):
    def run_(self, st):
        osc, hits = overlay(ET.fromstring(XML), json.loads(CFG.read_text()), st)
        return {w.get("id"): {t.get("k"): t.get("v") for t in w.findall("tag")} for w in osc.iter("way")}, hits

    def test_adds_missing_tags_only_on_motorways(self):
        ways, _ = self.run_({"confirmed"})
        self.assertEqual(ways["1"]["motorcycle"], "no")
        self.assertEqual(ways["1"]["bicycle"], "no")
        self.assertEqual(ways["2"]["motorcycle"], "yes")  # never overrides
        self.assertEqual(ways["2"]["bicycle"], "no")
        self.assertNotIn("3", ways)  # not a motorway
        self.assertNotIn("4", ways)  # bikes allowed there

    def test_approved_rules_add_motorcycle_only(self):
        ways, _ = self.run_({"confirmed", "user-approved-2026-11-19"})
        self.assertEqual(ways["5"], {"highway": "motorway", "name": "Yamuna Expressway", "motorcycle": "no"})

    def test_unapproved_status_off(self):
        ways, _ = self.run_({"confirmed"})
        self.assertNotIn("5", ways)

    def test_bbox_and_highway_class(self):
        ways, _ = self.run_({"confirmed"})
        self.assertEqual(ways["6"]["motorcycle"], "no")  # trunk inside Mumbai bbox
        self.assertNotIn("7", ways)  # same name, Delhi: outside bbox
        self.assertNotIn("8", ways)  # unrelated name

    def test_user_approved_expressways(self):
        ways, _ = self.run_({"user-approved-2026-11-19"})
        for i in (10, 11, 13, 15, 18, 19):
            self.assertEqual(ways[str(i)]["motorcycle"], "no", i)
        self.assertNotIn("bicycle", ways["11"])
        self.assertNotIn("17", ways)  # already tagged: never overridden
        for i in (9, 12, 14, 16, 20):  # urban DND flyway, confirmed-rule way, other expressway, not a motorway, NH44
            self.assertNotIn(str(i), ways, i)

    def test_every_rule_has_source_and_status(self):
        for r in json.loads(CFG.read_text())["rules"]:
            self.assertIn(r["status"], ("confirmed", "user-approved-2026-11-19", "assumed"))
            self.assertTrue(r["source"])

if __name__ == "__main__":
    unittest.main()
