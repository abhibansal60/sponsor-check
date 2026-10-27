# Sponsor check

Does this company sponsor work visas? Sponsor check searches the UK Home Office register of licensed sponsors and USCIS H-1B approvals by company name.

- Web: https://abhibansal.dev/sponsor-check/ (rebuilt daily from the official files)
- CLI: one Python file, standard library only

## Start here: paste this to your agent

```text
Set up Sponsor check (https://github.com/abhibansal60/sponsor-check) for me.
1. Clone it and run `python3 test_sponsor_check.py`. It needs Python 3.9+ and nothing else.
2. Run `python3 sponsor_check.py build` to download the UK register and combine it with the US H-1B
   snapshot into site/data.json.
3. Ask me which companies I'm applying to, or read them from my job tracker if I point you at one
   (read-only). Run `python3 sponsor_check.py "<company>" ...` for each and give me a table:
   company, UK licensed sponsor (legal name, routes), US H-1B approvals.
4. Flag any match whose legal name might be a different company with a similar name.
Don't change any of my files without asking.
```

## CLI

```bash
python3 sponsor_check.py "Thought Machine" "Glean"
```

```
Thought Machine:
  UK licensed sponsor (A rating, register 2026-10-23): Thought Machine Group Limited, London [Skilled Worker]
  US: no H-1B approvals in FY2025 (newer companies may sponsor now)
Glean:
  UK: not on the register of licensed sponsors (2026-10-23)
  US H-1B approvals FY2025: 25 (GLEAN TECHNOLOGIES INC, Palo Alto, CA)
```

`--json` prints the same as JSON. The first lookup downloads the UK register (about 11 MB, 5 seconds), and lookups rebuild it once it is more than 2 days old. `python3 sponsor_check.py build` forces a rebuild.

Matching ignores case, accents, punctuation, spaces and filler words such as Ltd, Inc, AG and UK, then matches whole words from the start of the legal name: "Palantir" finds Palantir UK Limited and Palantir Technologies UK Limited, "J.P. Morgan" finds JPMorgan Chase, but "Anthropic" doesn't find a philanthropic trust. A trading name after "t/a", "trading as" or "dba" is searchable too, so "Deliveroo" finds Roofoods Ltd t/a Deliveroo; legal-name matches are listed first. Always check that the legal name is the company you mean.

## What the data means

- **UK:** an employer on the register holds a sponsor licence for the listed routes (Skilled Worker is the usual one for tech jobs). The register is the Home Office's [register of licensed sponsors: workers](https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers), published under the Open Government Licence v3.0. A licence doesn't mean every role is open to sponsorship.
- **US:** H-1B petitions USCIS approved for the employer in fiscal year 2025 (all approval types: new employment, continuation, change of employer and so on), from the [H-1B Employer Data Hub](https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub). USCIS publishes FY2024 onwards only in the hub's Tableau workbook, whose "H1B Public" crosstab downloads as a ~95 MB CSV, so the repo keeps a per-employer total in `us-h1b.csv`. To move to a newer year once USCIS finishes it, set `US_YEAR` in `sponsor_check.py` and run `python3 sponsor_check.py us-snapshot`. Companies founded or hiring abroad since then won't appear even if they sponsor now.

Not legal advice.

## Develop

```bash
python3 test_sponsor_check.py              # matching rules
python3 sponsor_check.py build             # site/data.json
python3 -m http.server -d site 8000        # web page at http://localhost:8000
```

`.github/workflows/pages.yml` runs the tests, rebuilds the data every day and deploys `site/` to GitHub Pages. The web page uses the same filler-word list as the CLI, shipped inside `data.json`.

## License

MIT for the code. The data belongs to its publishers (UK Home Office, USCIS).
