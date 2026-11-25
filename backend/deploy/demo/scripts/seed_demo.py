"""Seed the Moimio demo workspace through the public API.

Builds three fictional events on an EMPTY Moimio instance:

  * "Youth Retreat 2027"   (English, the main demo event)
      - registration form with gender, date of birth, church, a conditional
        dietary follow-up question and a T-shirt size
      - 51 registrations (families such as the Parks and the Schmidts,
        friend groups linked by group code)
      - marks "Leader" (split across small groups) and "Worship team"
        (kept together)
      - group type "Rooms": 5 male, 6 female and 2 family rooms, filled by
        the allocation engine
      - group type "Small groups": 6 groups, filled by the allocation engine
      - 3 late sign-ups left unassigned (visible in the pool)
      - check-in: about half checked in, check-in columns "Paid" and
        "Welcome pack" ticked for some people
  * "Jugendfreizeit 2027"      (German registration form, no people)
  * "청년부 여름 수련회 2027"  (Korean registration form, no people)

Every name is invented and every address is @example.org.

Usage:
    export MOIMIO_URL=http://127.0.0.1:8000
    export MOIMIO_ADMIN_PASSWORD='...'        # Super Admin to create / log in as
    python seed_demo.py [--state state.json]

Optional:
    DEMO_START_DATE / DEMO_END_DATE   event dates, default 2027-07-23 / 2027-07-27
                                      (post_restore.py can move them later)

The instance should be empty (no events). The script is deterministic
(fixed random seeds), so re-running it on a fresh instance gives the same
people, rooms and check-in pattern; only ids and timestamps differ.
Registrations go through the public form endpoint, so if the backend runs
with RATE_LIMIT_REGISTRATION > 0 the script waits and retries when limited
(set RATE_LIMIT_REGISTRATION=0 on the seeding instance to make it fast).
"""
import argparse
import json
import os
import random

from moimio_api import ensure_admin, login, req

START = os.environ.get("DEMO_START_DATE", "2027-07-23")
END = os.environ.get("DEMO_END_DATE", "2027-07-27")

M, F = "male", "female"


# ─── Events and registration forms ──────────────────────────────────────────

def make_event(name, location, desc, tz, custom):
    """Create an event, configure its form, confirm setup, open registration."""
    e = req("POST", "/api/events/", json={
        "name": name, "location": location, "timezone": tz,
        "start_date": START, "end_date": END, "description": desc})
    eid = e["id"]
    req("PUT", f"/api/events/{eid}/fields", json=[
        {"field_name": "gender", "is_enabled": True, "is_required": True},
        {"field_name": "date_of_birth", "is_enabled": True, "is_required": False},
        {"field_name": "phone", "is_enabled": False},
        {"field_name": "address", "is_enabled": False},
        {"field_name": "country", "is_enabled": False},
        {"field_name": "church_organisation", "is_enabled": True, "is_required": False}])
    ids = {}
    for cf in custom:
        cf = dict(cf)
        if "if" in cf:  # conditional follow-up: shown only when an earlier select matches
            src, vals = cf.pop("if")
            cf["show_if"] = {"match": "all", "conditions": [
                {"source": ids[src], "op": "one_of", "value": vals}]}
        ids[cf["label"]] = req("POST", f"/api/events/{eid}/custom-fields/", json=cf)["id"]
    req("POST", f"/api/events/{eid}/setup/confirm/details")
    req("POST", f"/api/events/{eid}/setup/confirm/registration")
    req("POST", f"/api/events/{eid}/registration/open")
    return eid, ids


EN_FIELDS = [
    {"label": "Dietary needs", "field_type": "select", "is_required": True,
     "options": ["None", "Vegetarian", "Vegan", "Gluten-free", "Halal", "Other"]},
    {"label": "Allergies or other dietary details", "field_type": "text",
     "if": ("Dietary needs", ["Other"])},
    {"label": "T-shirt size", "field_type": "select", "options": ["XS", "S", "M", "L", "XL"]},
]
DE_FIELDS = [
    {"label": "Ernährung", "field_type": "select", "is_required": True,
     "options": ["Keine Besonderheiten", "Vegetarisch", "Vegan", "Glutenfrei", "Sonstiges"]},
    {"label": "Allergien oder weitere Hinweise zur Ernährung", "field_type": "text",
     "if": ("Ernährung", ["Sonstiges"])},
    {"label": "T-Shirt-Größe", "field_type": "select", "options": ["XS", "S", "M", "L", "XL"]},
]
KO_FIELDS = [
    {"label": "식단 요구사항", "field_type": "select", "is_required": True,
     "options": ["없음", "채식", "비건", "글루텐 프리", "기타"]},
    {"label": "알레르기 또는 기타 식단 정보", "field_type": "text", "if": ("식단 요구사항", ["기타"])},
    {"label": "티셔츠 사이즈", "field_type": "select", "options": ["XS", "S", "M", "L", "XL"]},
]

# ─── People (first, last, gender, date of birth, options) ───────────────────
# `group` links people by group code: the first person with a given key gets
# a fresh code from Moimio, everyone after them registers with that code.
PEOPLE = [
    ("Samuel", "Okafor", M, "1999-03-14", {}),
    ("Chloe", "Bennett", F, "2001-06-02", {"group": "BENNETT"}),
    ("David", "Park", M, "1981-09-21", {"group": "PARK", "church": "Korean Church of London"}),
    ("Sunhee", "Park", F, "1983-02-11", {"group": "PARK", "church": "Korean Church of London", "diet": "Vegetarian"}),
    ("Joshua", "Park", M, "2011-05-30", {"group": "PARK", "church": "Korean Church of London"}),
    ("Hannah", "Park", F, "2013-12-08", {"group": "PARK", "church": "Korean Church of London"}),
    ("Lukas", "Hoffmann", M, "2002-01-19", {"group": "HOFFMANN"}),
    ("Sophie", "Wagner", F, "2003-04-25", {"group": "WAGNER"}),
    ("Ethan", "Brooks", M, "2004-08-07", {"group": "BROOKS"}),
    ("Amara", "Osei", F, "2000-11-30", {}),
    ("Minjun", "Lee", M, "2001-07-16", {"church": "Korean Church of London"}),
    ("Zoe", "Patel", F, "2001-10-09", {"group": "BENNETT"}),
    ("Felix", "Braun", M, "2002-05-03", {"group": "HOFFMANN"}),
    ("Jiwoo", "Kim", F, "2003-02-27", {"group": "KIM", "church": "Korean Church of London"}),
    ("Daniel", "Reyes", M, "1997-12-12", {}),
    ("Lea", "Schulz", F, "2003-09-18", {"group": "WAGNER"}),
    ("Caleb", "Turner", M, "2004-03-22", {"group": "BROOKS"}),
    ("Ruth", "Adeyemi", F, "1996-07-04", {}),
    ("Markus", "Schmidt", M, "1979-10-01", {"group": "SCHMIDT"}),
    ("Katrin", "Schmidt", F, "1980-06-14", {"group": "SCHMIDT", "diet": "Gluten-free"}),
    ("Lena", "Schmidt", F, "2012-08-29", {"group": "SCHMIDT"}),
    ("Noah", "Fischer", M, "2002-11-11", {}),
    ("Grace", "Liu", F, "1998-01-23", {}),
    ("Mateo", "García", M, "2003-06-06", {}),
    ("Seoyeon", "Yoon", F, "2002-12-01", {"group": "KIM", "church": "Korean Church of London"}),
    ("Isaac", "Mensah", M, "2000-02-15", {}),
    ("Mia", "Schneider", F, "2004-05-20", {}),
    ("Tobias", "Krüger", M, "2002-09-09", {"group": "HOFFMANN"}),
    ("Freya", "Collins", F, "2001-03-03", {"group": "BENNETT"}),
    ("Joel", "Andersson", M, "1999-08-28", {}),
    ("Isabel", "Moreno", F, "2000-04-17", {}),
    ("Seojun", "Choi", M, "2001-01-08", {"church": "Korean Church of London"}),
    ("Esther", "Bae", F, "2003-07-12", {"group": "KIM", "church": "Korean Church of London"}),
    ("Aaron", "Whitfield", M, "1995-05-27", {}),
    ("Leonie", "Richter", F, "2003-10-30", {"group": "WAGNER"}),
    ("Liam", "O'Connor", M, "2003-12-19", {}),
    ("Emma", "Lindgren", F, "2002-02-08", {}),
    ("Jamal", "Hughes", M, "2001-09-01", {}),
    ("Naomi", "Fraser", F, "1999-11-05", {}),
    ("Benjamin", "Wright", M, "2004-01-14", {}),
    ("Priya", "Sharma", F, "2002-06-21", {"diet": "Vegetarian"}),
    ("Elias", "Novak", M, "2000-10-26", {}),
    ("Clara", "Hartmann", F, "2001-08-11", {}),
    ("Kai", "Nakamura", M, "2003-03-29", {}),
    ("Abigail", "Moore", F, "2004-07-07", {}),
    ("Oliver", "Grant", M, "2002-04-04", {}),
    ("Lydia", "Evans", F, "2000-12-24", {}),
    ("Rebecca", "Osborne", F, "2003-05-15", {}),
]
# Registered after the allocation, so they show up unassigned in the pool.
LATE = [
    ("Rafael", "Costa", M, "2002-02-02", {"diet": "None", "church": "Riverside Church", "size": "M"}),
    ("Ingrid", "Larsen", F, "2003-08-19", {"diet": "Vegetarian", "church": "Riverside Church", "size": "M"}),
    ("Yuna", "Han", F, "2004-04-12", {"diet": "None", "church": "Riverside Church", "size": "M"}),
]
LEADERS = ["Samuel Okafor", "Chloe Bennett", "Daniel Reyes", "Ruth Adeyemi", "Aaron Whitfield", "Grace Liu"]
WORSHIP = ["Minjun Lee", "Amara Osei", "Joel Andersson", "Isabel Moreno"]

DIETS = ["None"] * 9 + ["Vegetarian", "Vegetarian", "Vegan", "Gluten-free", "Halal"]
CHURCHES = ["Grace Community Church", "St. Andrew's Fellowship", "Riverside Church",
            "Hope City Church", "Korean Church of London"]


def email_for(first, last):
    local = f"{first}.{last}".lower()
    for a, b in (("'", ""), ("ü", "ue"), ("ö", "oe"), ("í", "i")):
        local = local.replace(a, b)
    return local + "@example.org"


def register(eid, cf, codes, first, last, gender, dob, opt):
    group = opt.get("group")
    body = {
        "first_name": first, "last_name": last, "email": email_for(first, last),
        "gender": gender, "date_of_birth": dob,
        "church_organisation": opt.get("church") or random.choice(CHURCHES),
        "gdpr_consent": True,
        # first member: the key is the stem Moimio builds the code from (PARK-123)
        "group_code": (codes.get(group) or group) if group else None,
        "custom_fields": {
            cf["Dietary needs"]: opt.get("diet") or random.choice(DIETS),
            cf["T-shirt size"]: opt.get("size") or random.choice(["S", "M", "M", "L", "L", "XL"]),
        },
    }
    p = req("POST", f"/api/events/{eid}/register", json=body)
    if group and group not in codes:
        codes[group] = p["group_code"]
    return p


def commit_engine(eid, cat_id, mode):
    """Run the allocation engine for one group type and commit its proposal."""
    r = req("POST", f"/api/events/{eid}/allocation-categories/{cat_id}/suggest", params={"mode": mode})
    req("POST", f"/api/events/{eid}/allocation-categories/{cat_id}/commit", json={
        "proposed": r["proposed"], "placement_reasons": r.get("placement_reasons"),
        "engine_run_id": r.get("run_id")})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", help="write created ids to this JSON file")
    args = ap.parse_args()

    random.seed(2027)
    ensure_admin()
    login()
    if req("GET", "/api/events/"):
        raise SystemExit("This instance already has events; seed an empty instance.")

    eid, cf = make_event("Youth Retreat 2027", "Lakeside Retreat Centre, Windermere",
                         "Five days of worship, teaching and fun by the lake.", "Europe/London", EN_FIELDS)
    eid_de, _ = make_event("Jugendfreizeit 2027", "Freizeitheim am See",
                           "Fünf Tage Gemeinschaft am See.", "Europe/Berlin", DE_FIELDS)
    eid_ko, _ = make_event("청년부 여름 수련회 2027", "호숫가 수련원",
                           "호숫가에서 함께하는 5일간의 수련회", "Asia/Seoul", KO_FIELDS)

    # People
    codes, people = {}, {}
    for first, last, g, dob, opt in PEOPLE:
        people[f"{first} {last}"] = register(eid, cf, codes, first, last, g, dob, opt)
    print(f"registered {len(people)} people")

    # Marks
    leader = req("POST", f"/api/events/{eid}/marks/", json={"name": "Leader", "colour": "#C8102E", "cluster_behaviour": "split"})
    worship = req("POST", f"/api/events/{eid}/marks/", json={"name": "Worship team", "colour": "#2E8B57", "cluster_behaviour": "together"})
    for mark, names in ((leader, LEADERS), (worship, WORSHIP)):
        for n in names:
            req("POST", f"/api/events/{eid}/marks/{mark['id']}/assign", json={"participant_id": people[n]["id"]})

    # Group types: the two defaults every event starts with
    cats = {c["name_key"]: c for c in req("GET", f"/api/events/{eid}/allocation-categories/")}
    rooms, groups = cats["rooms"], cats["small_groups"]
    units = f"/api/events/{eid}/allocation-categories/{rooms['id']}/units/"
    req("POST", units, json={"name": "Family Room 1", "capacity": 5, "sort_order": 1})
    req("POST", units, json={"name": "Family Room 2", "capacity": 4, "sort_order": 2})
    for i in range(1, 6):
        req("POST", units, json={"name": f"Cedar {i}", "capacity": 4, "gender_restriction": "male", "sort_order": 10 + i})
    for i in range(1, 7):
        req("POST", units, json={"name": f"Willow {i}", "capacity": 4, "gender_restriction": "female", "sort_order": 20 + i})
    for i, name in enumerate(["Group A", "Group B", "Group C", "Group D", "Group E", "Group F"]):
        req("POST", f"/api/events/{eid}/allocation-categories/{groups['id']}/units/",
            json={"name": name, "capacity": 9, "sort_order": i})
    gs = dict(groups.get("settings") or {})
    eng = dict(gs.get("engine") or {})
    eng["mark_priorities"] = [{"id": leader["id"], "behaviour": "split"},
                              {"id": worship["id"], "behaviour": "together"}]
    gs["engine"] = eng
    req("PATCH", f"/api/events/{eid}/allocation-categories/{groups['id']}", json={"settings": gs})

    # Allocation: rooms, then small groups (same as Auto-Allocate + Commit in the UI)
    commit_engine(eid, rooms["id"], "top_up")
    commit_engine(eid, groups["id"], "replace")
    print("rooms and small groups allocated")

    # Late sign-ups (stay unassigned)
    random.seed(7)
    for first, last, g, dob, opt in LATE:
        people[f"{first} {last}"] = register(eid, cf, codes, first, last, g, dob, opt)

    # Check-in: odd participant numbers up to 49 plus #8, #16, #20 are in
    random.seed(11)
    fields = {f["field_name"]: f for f in req("GET", f"/api/events/{eid}/checkin-fields/")}
    for name, order in (("Paid", 0), ("Welcome pack", 1)):
        if name not in fields:
            fields[name] = req("POST", f"/api/events/{eid}/checkin-fields/", json={"field_name": name, "sort_order": order})
    ps = sorted(req("GET", f"/api/events/{eid}/participants"), key=lambda p: p["participant_number"])
    checked = {p["id"] for p in ps
               if (p["participant_number"] % 2 == 1 and p["participant_number"] <= 49)
               or p["participant_number"] in (8, 16, 20)}
    for p in ps:
        ci = p["id"] in checked
        paid = (ci and random.random() < 0.85) or (not ci and random.random() < 0.35)
        req("POST", f"/api/participants/{p['id']}/checkin", json={"checked_in": ci})
        req("POST", f"/api/events/{eid}/checkin-values/", json={
            "participant_id": p["id"], "field_id": fields["Welcome pack"]["id"], "checked": ci and random.random() < 0.8})
        req("POST", f"/api/events/{eid}/checkin-values/", json={
            "participant_id": p["id"], "field_id": fields["Paid"]["id"], "checked": paid})
    print(f"checked in {len(checked)} of {len(ps)}")

    if args.state:
        with open(args.state, "w") as fh:
            json.dump({"event_id": eid, "event_de": eid_de, "event_ko": eid_ko,
                       "rooms": rooms["id"], "groups": groups["id"],
                       "leader": leader["id"], "worship": worship["id"], "codes": codes, "custom": cf,
                       "people": {k: v["id"] for k, v in people.items()}}, fh, indent=1, ensure_ascii=False)
    print("done; main event id", eid)


if __name__ == "__main__":
    main()
