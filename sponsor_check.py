#!/usr/bin/env python3
"""Does this employer sponsor work visas? Checks the UK register of licensed sponsors
and USCIS H-1B approvals. Standard library only.

    python3 sponsor_check.py build            # download the UK register, write site/data.json
    python3 sponsor_check.py us-snapshot      # re-download the US file into us-h1b.csv (rarely needed)
    python3 sponsor_check.py "Thought Machine" # look up an employer (rebuilds data if stale)
    python3 sponsor_check.py --json "Glean"    # same, as JSON
"""
import csv, io, json, os, re, sys, time, urllib.request
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "site", "data.json")
UK_PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
# USCIS publishes FY2024+ only inside a Tableau dashboard; FY2023 is the newest plain CSV.
# ponytail: US data is FY2023, swap in a newer source (DOL LCA disclosures) if one becomes scriptable.
US_YEAR = 2023
US_CSV = f"https://www.uscis.gov/sites/default/files/document/data/h1b_datahubexport-{US_YEAR}.csv"
# The FY2023 file never changes and USCIS returns 403 to GitHub Actions, so a per-employer
# snapshot is committed and builds read it from disk.
US_SNAPSHOT = os.path.join(ROOT, "us-h1b.csv")
STALE_DAYS = 2

# Words that don't identify an employer. Shipped inside data.json so the web page uses the same list.
DROP = ["limited", "ltd", "llc", "llp", "lp", "inc", "incorporated", "plc", "pbc", "corp",
        "corporation", "co", "company", "the", "uk", "us", "usa", "gmbh"]
_DROP = set(DROP)


def norm(name):
    words = re.sub(r"[^a-z0-9]+", " ", name.lower().replace("&", " and ")).split()
    return [w for w in words if w not in _DROP]


def matches(query, name):
    q, n = norm(query), norm(name)
    return bool(q) and (n[:len(q)] == q or "".join(n) == "".join(q))


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 sponsor-check"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read().decode("utf-8-sig", errors="replace")


def build_uk():
    page = fetch(UK_PAGE)
    url = re.search(r"https://assets\.publishing\.service\.gov\.uk/[^\"]+\.csv", page).group(0)
    orgs = defaultdict(lambda: [set(), set(), set()])  # towns, routes, ratings
    for row in csv.DictReader(io.StringIO(fetch(url))):
        name = row["Organisation Name"].strip()
        if not name:
            continue
        o = orgs[name]
        if row["Town/City"].strip():
            o[0].add(row["Town/City"].strip().title())
        o[1].add(row["Route"].strip())
        o[2].update(re.findall(r"([AB]) rating", row["Type & Rating"]))
    routes = sorted({r for _, r, _ in orgs.values() for r in r})  # 18 names, sent once as indexes
    rows = [[n, ", ".join(sorted(t)), [routes.index(x) for x in sorted(r)], "".join(sorted(g))]
            for n, (t, r, g) in orgs.items()]
    as_of = re.search(r"(\d{4}-\d{2}-\d{2})\.csv$", url)
    return sorted(rows), routes, as_of.group(1) if as_of else str(date.today())


def snapshot_us():
    emp = defaultdict(lambda: [0, ""])
    for row in csv.DictReader(io.StringIO(fetch(US_CSV))):
        name = row["Employer"].strip()
        if not name:
            continue
        approvals = int(row["Initial Approval"] or 0) + int(row["Continuing Approval"] or 0)
        e = emp[name]
        e[0] += approvals
        if row["City"] and not e[1]:
            e[1] = f'{row["City"].title()}, {row["State"]}'
    rows = sorted([n, a, place] for n, (a, place) in emp.items() if a)
    with open(US_SNAPSHOT, "w", newline="") as f:
        csv.writer(f).writerows([["employer", "approvals", "place"]] + rows)
    print(f"wrote {US_SNAPSHOT}: {len(rows)} employers (FY{US_YEAR})")


def build_us():
    with open(US_SNAPSHOT, newline="") as f:
        return [[r["employer"], int(r["approvals"]), r["place"]] for r in csv.DictReader(f)]


def build():
    uk, routes, uk_date = build_uk()
    us = build_us()
    data = {"built": str(date.today()), "uk_date": uk_date, "us_year": US_YEAR,
            "drop": DROP, "routes": routes, "uk": uk, "us": us}
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    tmp = f"{DATA}.{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, DATA)  # atomic: parallel batch workers may read while one rebuilds
    print(f"wrote {DATA}: {len(uk)} UK sponsors ({uk_date}), {len(us)} US employers (FY{US_YEAR})")


def load():
    if not os.path.exists(DATA) or time.time() - os.path.getmtime(DATA) > STALE_DAYS * 86400:
        build()
    with open(DATA) as f:
        return json.load(f)


def lookup(query, data=None):
    data = data or load()
    rank = lambda row: (norm(row[0]) != norm(query), len(row[0]))
    uk = sorted((r for r in data["uk"] if matches(query, r[0])), key=rank)
    us = sorted((r for r in data["us"] if matches(query, r[0])), key=rank)
    return {"query": query, "uk_date": data["uk_date"], "us_year": data["us_year"],
            "uk": [{"name": n, "town": t, "routes": [data["routes"][i] for i in r], "rating": g}
                   for n, t, r, g in uk[:10]],
            "us": [{"name": n, "approvals": a, "place": p} for n, a, p in us[:10]]}


def report(res):
    out = [f'{res["query"]}:']
    if res["uk"]:
        for o in res["uk"]:
            out.append(f'  UK licensed sponsor ({o["rating"]} rating, register {res["uk_date"]}): '
                       f'{o["name"]}, {o["town"]} [{"; ".join(o["routes"])}]')
    else:
        out.append(f'  UK: not on the register of licensed sponsors ({res["uk_date"]})')
    if res["us"]:
        for o in res["us"]:
            out.append(f'  US H-1B approvals FY{res["us_year"]}: {o["approvals"]} ({o["name"]}, {o["place"]})')
    else:
        out.append(f'  US: no H-1B approvals in FY{res["us_year"]} (newer companies may sponsor now)')
    return "\n".join(out)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["build"]:
        build()
    elif args == ["us-snapshot"]:
        snapshot_us()
    elif args and args[0] == "--json":
        print(json.dumps([lookup(q) for q in args[1:]], indent=1))
    elif args:
        data = load()
        print("\n".join(report(lookup(q, data)) for q in args))
    else:
        sys.exit(__doc__)
