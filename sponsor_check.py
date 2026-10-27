#!/usr/bin/env python3
"""Does this employer sponsor work visas? Checks the UK register of licensed sponsors
and USCIS H-1B approvals. Standard library only.

    python3 sponsor_check.py build            # download the UK register, write site/data.json
    python3 sponsor_check.py us-snapshot      # re-download the US file into us-h1b.csv (rarely needed)
    python3 sponsor_check.py "Thought Machine" # look up an employer (rebuilds data if stale)
    python3 sponsor_check.py --json "Glean"    # same, as JSON
"""
import csv, io, json, os, re, sys, time, unicodedata, urllib.request
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "site", "data.json")
UK_PAGE = "https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers"
# USCIS publishes FY2024+ only in the Data Hub's Tableau workbook. Its "H1B Public" crosstab
# exports as CSV for one fiscal year (the filter field name ends in three spaces). FY2025 is the
# newest complete year; the hub adds a quarter of the current year every few months.
US_YEAR = 2025
US_CSV = ("https://bigdataanalyticspub-sb.uscis.dhs.gov/views/H1BEmployerDataHub-Final/H1BPublic.csv"
          f"?Fiscal%20Year%20%20%20={US_YEAR}")
# A finished year never changes and the export is ~95 MB, so a per-employer snapshot is
# committed and builds read it from disk.
US_SNAPSHOT = os.path.join(ROOT, "us-h1b.csv")
STALE_DAYS = 2

# Words that don't identify an employer. Shipped inside data.json so the web page uses the same list.
DROP = ["limited", "ltd", "llc", "llp", "lp", "inc", "incorporated", "plc", "pbc", "corp",
        "corporation", "co", "company", "the", "uk", "us", "usa", "gmbh", "ag", "sa", "bv", "nv", "pty"]
_DROP = set(DROP)
# "Roofoods Ltd t/a Deliveroo": the trading name after the marker is searchable on its own.
TRADING_AS = re.compile(r"\b(?:t/as?|trading\s+as|d/b/a|d\.b\.a\.?|dba)(?!\w)", re.I)


def norm(name):
    s = unicodedata.normalize("NFKD", name.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # Société -> societe
    words = re.sub(r"[^a-z0-9]+", " ", re.sub(r"['’]", "", s).replace("&", " and ")).split()
    return [w for w in words if w not in _DROP]


def keys(name):
    """norm() of the legal name, plus of each part around a trading-as marker ("DBA Media Ltd" has none)."""
    parts = TRADING_AS.split(name)
    return [norm(name)] + ([norm(p) for p in parts] if len(parts) > 1 and parts[0].strip() else [])


def hit(q, n):
    """The query's letters, spaces ignored, run from the start of the name to the end of one of its words:
    'Palantir' finds Palantir UK Limited, 'J.P. Morgan' finds JPMorgan Chase, 'Notion' misses Notional."""
    qj, i = "".join(q), 0
    for w in n:
        if not qj.startswith(w, i):
            return False
        i += len(w)
        if i == len(qj):
            return True
    return False


def matches(query, name):
    q = norm(query)
    return any(hit(q, k) for k in keys(name))


def ratings(type_and_rating):
    """'Worker (A rating)', 'Worker (A (Premium))' -> {'A'}; 'Worker (UK Expansion Worker: Provisional )' -> {'Provisional'}."""
    found = set(re.findall(r"\b([AB])\s*(?:rating|\()", type_and_rating))
    return found or ({"Provisional"} if "provisional" in type_and_rating.lower() else set())


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
        o[2].update(ratings(row["Type & Rating"]))
    routes = sorted({r for _, r, _ in orgs.values() for r in r})  # 18 names, sent once as indexes
    rows = [[n, ", ".join(sorted(t)), [routes.index(x) for x in sorted(r)], ", ".join(sorted(g))]
            for n, (t, r, g) in orgs.items()]
    as_of = re.search(r"(\d{4}-\d{2}-\d{2})\.csv$", url)
    return sorted(rows), routes, as_of.group(1) if as_of else str(date.today())


def snapshot_us():
    emp = defaultdict(lambda: [0, ""])
    # Long format: one row per employer, tax ID, zip and measure ("New Employment Approval", ...).
    reader = csv.DictReader(io.StringIO(fetch(US_CSV)))
    if "Fiscal Year   " not in (reader.fieldnames or []):
        sys.exit(f"US export has no 'Fiscal Year   ' column (got {reader.fieldnames}): did the export change?")
    for row in reader:
        name = row["Employer (Petitioner) Name"].strip()
        if not name or not row["Measure Names"].endswith("Approval"):
            continue
        if row["Fiscal Year   "] != str(US_YEAR):
            sys.exit(f"US export returned FY{row['Fiscal Year   ']}, not FY{US_YEAR}: did the filter field change?")
        e = emp[name]
        e[0] += int(row["Measure Values"].replace(",", "") or 0)
        if row["Petitioner City"] and not e[1]:
            e[1] = ", ".join(filter(None, [row["Petitioner City"].title(), row["Petitioner State"]]))
    rows = sorted([n, a, place] for n, (a, place) in emp.items() if a)
    # A renamed measure or an empty crosstab must not wipe the committed snapshot.
    if os.path.exists(US_SNAPSHOT):
        with open(US_SNAPSHOT, newline="") as f:
            old = sum(1 for _ in f) - 1
        if len(rows) < old // 2:
            sys.exit(f"US export gave {len(rows)} employers, the snapshot has {old}: not overwriting it.")
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
    if not os.path.exists(DATA):
        build()
    elif time.time() - os.path.getmtime(DATA) > STALE_DAYS * 86400:
        try:
            build()
        except Exception as e:  # offline or gov.uk changed: old data beats no answer
            print(f"using data from {time.strftime('%Y-%m-%d', time.localtime(os.path.getmtime(DATA)))} ({e})", file=sys.stderr)
    with open(DATA) as f:
        return json.load(f)


def _keyed(rows, _cache={}):
    """[(keys(name), row)] once per row list: batch lookups no longer re-normalise 155k names per query."""
    if id(rows) not in _cache:
        _cache[id(rows)] = (rows, [(keys(r[0]), r) for r in rows])  # rows kept alive so the id stays theirs
    return _cache[id(rows)][1]


def lookup(query, data=None):
    data = data or load()
    q = norm(query)
    # Exact legal name, then legal names that start with the query, then trading names; shortest first.
    rank = lambda ks, r: ("".join(ks[0]) != "".join(q), not hit(q, ks[0]), len(r[0]))
    pick = lambda rows: [r for ks, r in sorted(((ks, r) for ks, r in _keyed(rows) if any(hit(q, k) for k in ks)),
                                               key=lambda x: rank(*x))]
    uk, us = pick(data["uk"]), pick(data["us"])
    return {"query": query, "uk_date": data["uk_date"], "us_year": data["us_year"],
            "uk": [{"name": n, "town": t, "routes": [data["routes"][i] for i in r], "rating": g}
                   for n, t, r, g in uk[:10]],
            "us": [{"name": n, "approvals": a, "place": p} for n, a, p in us[:10]]}


def report(res):
    out = [f'{res["query"]}:']
    if res["uk"]:
        for o in res["uk"]:
            out.append(f'  UK licensed sponsor ({o["rating"] or "no"} rating, register {res["uk_date"]}): '
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
