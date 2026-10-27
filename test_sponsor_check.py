from sponsor_check import lookup, matches, norm, ratings

assert norm("Databricks UK Limited") == ["databricks"]
assert norm("AT&T Inc.") == ["at", "and", "t"]
assert matches("Anthropic", "Anthropic Limited")
assert matches("Anthropic", "ANTHROPIC PBC D B A ANTHROPIC INC")
assert not matches("Anthropic", "MARGARET A CARGILL PHILANTHROPIC SERVICES LLC")
assert matches("Thought Machine", "Thought Machine Group Limited")
assert matches("ElevenLabs", "Eleven Labs Inc")
assert not matches("Notion", "Notional Partners Ltd")
assert not matches("Limited", "Anthropic Limited")  # query of only filler words matches nothing
# Tricky names
assert matches("Acme Ltd", "ACME LIMITED")
assert matches("Marks & Spencer", "Marks and Spencer Group Plc")
assert matches("Société Générale", "Societe Generale London Branch")  # accents
assert matches("Nestlé", "Nestle UK Limited")
assert matches("Loreal", "L'Oréal UK Ltd")
assert matches("J.P. Morgan", "JPMorgan Chase Bank, National Association")  # initials, spaced or not
assert matches("JPMorgan", "J.P. Morgan Securities plc")
assert matches("Deutsche Bank AG", "DEUTSCHE BANK SECURITIES INC")
assert matches("Deliveroo", "Roofoods Ltd t/a Deliveroo")  # trading names
assert matches("Roofoods", "Roofoods Ltd t/a Deliveroo")
assert matches("Kamran Tandoori", "GSK SERENE LTD T/A KAMRAN TANDOORI")
assert matches("Procogia", "0965688 BC LTD DBA PROCOGIA")
assert matches("Cherry Tree Care Home", "Dreams Care Homes Limited T/As Cherry Tree Care Home")
assert matches("Foo", "Bar Limited trading as Foo")
assert not matches("Smith", "T A Smith Ltd")  # initials, not "t/a"
assert not matches("Media", "DBA Media Ltd")  # a name that starts with DBA is not a trading name
assert matches("DBA Media", "DBA Media Ltd")
assert matches("Deliveroo", "Roofoods Ltd d.b.a. Deliveroo")
assert matches("Deliveroo", "Roofoods Ltd trading  as Deliveroo")
assert not matches("Notion", "No Tional Ltd")

data = {"uk_date": "2026-10-02", "us_year": 2023, "routes": ["Skilled Worker"],
        "uk": [["Palantir UK Limited", "London", [0], "A"],
               ["Palantir Technologies UK Limited", "London", [0], "A"]],
        "us": [["GLEAN TECHNOLOGIES INC", 5, "Palo Alto, CA"]]}
r = lookup("Palantir Technologies", data)
assert [o["name"] for o in r["uk"]] == ["Palantir Technologies UK Limited"]
r = lookup("Palantir", data)
assert r["uk"][0]["name"] == "Palantir UK Limited"  # shortest close match first
assert lookup("Glean", data)["us"][0]["approvals"] == 5
data = {**data, "uk": data["uk"] + [["Roofoods Ltd t/a Deliveroo", "London", [0], "A"]]}  # new list: lookups cache by id
assert [o["name"] for o in lookup("Deliveroo", data)["uk"]] == ["Roofoods Ltd t/a Deliveroo"]
data = {**data, "uk": data["uk"] + [["Lansia Limited T/A McDonalds", "Leeds", [0], "A"],
                                    ["McDonald's Restaurants Limited", "London", [0], "A"]]}
assert [o["name"] for o in lookup("McDonald's", data)["uk"]] == ["McDonald's Restaurants Limited", "Lansia Limited T/A McDonalds"]  # legal names first
assert lookup("Vapi", data) == {"query": "Vapi", "uk_date": "2026-10-02", "us_year": 2023, "uk": [], "us": []}
assert ratings("Worker (A rating)") == {"A"}
assert ratings("Worker (A (Premium))") == {"A"}  # Google's row: showed " rating" before
assert ratings("Temporary Worker (B rating)") == {"B"}
assert ratings("Worker (UK Expansion Worker: Provisional )") == {"Provisional"}

# snapshot_us on a tiny export: sums approval measures only, no dangling comma, guards the snapshot.
import csv, os, tempfile
import sponsor_check as sc
H = '"Fiscal Year   ","Employer (Petitioner) Name","Petitioner City","Petitioner State","Measure Names","Measure Values"\n'
sc.US_SNAPSHOT = os.path.join(tempfile.mkdtemp(), "us.csv")
sc.fetch = lambda url: H + ('2025,ACME INC,Austin,TX,New Employment Approval,"1,200"\n'
                            '2025,ACME INC,Austin,TX,Continuation Approval,3\n'
                            '2025,ACME INC,Austin,TX,New Employment Denial,9\n'
                            '2025,BETA LLC,Hillsboro,,New Employment Approval,2\n')
sc.snapshot_us()
assert list(csv.reader(open(sc.US_SNAPSHOT, newline=""))) == [
    ["employer", "approvals", "place"], ["ACME INC", "1203", "Austin, TX"], ["BETA LLC", "2", "Hillsboro"]]
for export in (H, H.replace("Fiscal Year   ", "Fiscal Year"), H + "2026,ACME INC,Austin,TX,New Employment Approval,1\n"):
    sc.fetch = lambda url: export
    try:
        sc.snapshot_us()
        raise AssertionError("snapshot_us accepted a bad export")
    except SystemExit:
        pass
assert len(list(csv.reader(open(sc.US_SNAPSHOT, newline="")))) == 3  # untouched
print("ok")
