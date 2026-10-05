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

data = {"uk_date": "2026-10-02", "us_year": 2023, "routes": ["Skilled Worker"],
        "uk": [["Palantir UK Limited", "London", [0], "A"],
               ["Palantir Technologies UK Limited", "London", [0], "A"]],
        "us": [["GLEAN TECHNOLOGIES INC", 5, "Palo Alto, CA"]]}
r = lookup("Palantir Technologies", data)
assert [o["name"] for o in r["uk"]] == ["Palantir Technologies UK Limited"]
r = lookup("Palantir", data)
assert r["uk"][0]["name"] == "Palantir UK Limited"  # shortest close match first
assert lookup("Glean", data)["us"][0]["approvals"] == 5
assert lookup("Vapi", data) == {"query": "Vapi", "uk_date": "2026-10-02", "us_year": 2023, "uk": [], "us": []}
assert ratings("Worker (A rating)") == {"A"}
assert ratings("Worker (A (Premium))") == {"A"}  # Google's row: showed " rating" before
assert ratings("Temporary Worker (B rating)") == {"B"}
assert ratings("Worker (UK Expansion Worker: Provisional )") == {"Provisional"}
print("ok")
