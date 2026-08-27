# Pending Terms (待审核术语)

Terms discovered during translation that need verification.
After verification, move confirmed entries to the appropriate reference file.

Entry template (`learn.py --auto` writes this shape). Add real entries
flush-left (`### ` at column 0) so learn.py / health_check can parse them;
this template itself is shown indented on purpose so parsers do not count it
as an entry:

    ### <English term or card name>
    - Type: card | phrase | abbrev
    - Suggested: (translate and verify)
    - Confidence: low
    - Discovered: YYYY-MM-DD
    - Status: pending review

Rules for confirming:
1. Verify the Chinese translation against server card data or official sources
2. Check if the term already exists under a different name
3. Update this file: change Status to `confirmed` and add `Confirmed: YYYY-MM-DD`
4. Move the entry to the appropriate reference file (terminology_map.md, card_overrides.md, etc.)
5. Run `python scripts/check_translation.py` to verify no conflicts

---

# (empty — all pending terms reviewed and resolved)
