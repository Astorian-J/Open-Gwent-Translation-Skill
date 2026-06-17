#!/usr/bin/env python3
"""Shared utilities for gwent-translation-style scripts.

Extracted to eliminate duplication of proper-noun extraction logic
across learn.py, context_lock.py, and diff_review.py.
"""

import re
import sys
from collections.abc import Iterator
from typing import Any

# --- JSON output helper (agent-agnostic) ---


def json_output(data: Any, errors: list[str] | None = None, exit_code: int = 0) -> None:
    """Print a standard JSON envelope to stdout and exit.

    Args:
        data: Command-specific structured payload.
        errors: High-level error messages (not individual translation issues).
        exit_code: Process exit code. 0 means success; non-zero means failure.
    """
    import json

    if errors is None:
        errors = []

    envelope = {
        "success": exit_code == 0,
        "exit_code": exit_code,
        "data": data,
        "errors": errors,
    }

    print(json.dumps(envelope, ensure_ascii=False, indent=2))
    sys.exit(exit_code)


# --- Regex patterns ---

CARD_NAME_PATTERN = re.compile(
    r'\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,2}:\s*(?:The\s+)?'
    r'[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,2})\b'
)

ABBREVIATION_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')

# Function words (articles, prepositions, conjunctions) that can appear
# between capitalized words in card names (e.g., "Geralt of Rivia",
# "Filavandrel aén Fidháil", "Horst Borsodi").
FUNCTION_WORDS: frozenset[str] = frozenset({
    "of", "the", "in", "a", "an", "to", "for", "and", "or",
    "de", "en", "el", "il", "la", "na", "van", "von", "zu",
    "var", "aep", "di", "du", "del", "den", "der", "dos",
    "aén", "áen",  # Elven function words (e.g., Filavandrel aén Fidháil)
})

# --- Skip sets ---

# Minimal skip words used by context_lock.py and diff_review.py.
SKIP_WORDS_MINIMAL: frozenset[str] = frozenset({
    "The", "This", "That", "These", "Those", "They", "There", "Then",
    "When", "What", "Where", "Which", "While", "Although", "However",
})

# Full skip words used by learn.py for false-positive filtering.
# Kept intentionally small and focused on words that are genuinely not Gwent terms.
# Common adjective/adverb comparative/superlative forms are filtered via regex in
# the extraction functions rather than being enumerated here.
SKIP_WORDS_FULL: frozenset[str] = frozenset({
    # Articles and determiners
    "The", "A", "An", "This", "That", "These", "Those", "It", "Its",
    "Such", "Each", "Every", "All", "Both", "Either", "Neither",
    # Personal pronouns
    "He", "She", "They", "We", "You", "I", "Me", "My", "His", "Her",
    "Their", "Our", "Your", "One", "Ones",
    # Common conjunctions
    "And", "Or", "But", "If", "Then", "Than", "Because", "Since", "Until",
    "Although", "However", "Therefore", "While", "Whereas",
    # Common interrogatives / relatives
    "When", "Where", "Why", "How", "What", "Who", "Which", "Whose", "Whom",
    # Common prepositions
    "In", "On", "At", "To", "For", "Of", "With", "From", "By", "About",
    "Into", "Onto", "Upon", "Over", "Under", "Above", "Below", "Between",
    "Among", "Through", "Throughout", "Across", "Along", "Against", "Toward",
    "Towards", "Before", "After", "During", "Within", "Without", "Behind",
    "Beyond", "Beside", "Besides", "Inside", "Outside", "Off", "Up", "Down",
    "Like", "As", "Near", "Around",
    # Common adverbs
    "Very", "Quite", "Rather", "Really", "Just", "Only", "Also", "Too",
    "Even", "Still", "Yet", "Already", "Always", "Never", "Often", "Sometimes",
    "Usually", "Maybe", "Perhaps", "Probably", "Possibly", "Certainly",
    "Definitely", "Actually", "Basically", "Essentially", "Generally",
    "Typically", "Finally", "Eventually", "Previously", "Currently",
    # Common generic adjectives
    "New", "Old", "Good", "Bad", "Big", "Small", "Long", "Short", "High",
    "Low", "Great", "Little", "Large", "Many", "Much", "More", "Most",
    "Some", "Any", "Other", "Another", "Same", "Different", "Own",
    "First", "Second", "Third", "Last", "Next", "Previous",
    # Common generic verbs / verb forms that are not card names
    "Is", "Are", "Was", "Were", "Be", "Been", "Being", "Have", "Has", "Had",
    "Do", "Does", "Did", "Done", "Get", "Gets", "Got", "Gotten", "Make",
    "Makes", "Made", "Take", "Takes", "Took", "Taken", "Come", "Comes", "Came",
    "Go", "Goes", "Went", "Gone", "See", "Sees", "Saw", "Seen", "Know",
    "Knows", "Knew", "Known", "Think", "Thinks", "Thought", "Use", "Uses",
    "Used", "Find", "Finds", "Found", "Give", "Gives", "Gave", "Given",
    "Tell", "Tells", "Told", "Work", "Works", "Worked", "Call", "Calls",
    "Called", "Try", "Tries", "Tried", "Need", "Needs", "Needed", "Feel",
    "Feels", "Felt", "Become", "Becomes", "Became", "Become", "Leave",
    "Leaves", "Left", "Put", "Puts", "Mean", "Means", "Meant", "Keep",
    "Keeps", "Kept", "Let", "Lets", "Begin", "Begins", "Began", "Begun",
    "Seem", "Seems", "Seemed", "Help", "Helps", "Helped", "Show", "Shows",
    "Showed", "Shown", "Hear", "Hears", "Heard", "Play", "Plays", "Played",
    "Run", "Runs", "Ran", "Move", "Moves", "Moved", "Live", "Lives", "Lived",
    "Believe", "Believes", "Believed", "Bring", "Brings", "Brought",
    "Happen", "Happens", "Happened", "Stand", "Stands", "Stood",
    # Numbers as words
    "Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
    "Nine", "Ten", "Eleven", "Twelve", "Twenty", "Thirty", "Hundred",
    "Thousand", "Million",
})


# Pattern for common English comparative/superlative adjectives and adverbs.
# Used as a fallback filter so the literal skip list does not need to enumerate
# every possible form.
_SKIP_COMPARATIVE_RE = re.compile(r'^[A-Z][a-z]+(er|est)$')


def is_likely_common_word(word: str) -> bool:
    """Return True if word looks like a common English word, not a card name.

    Combines the curated skip list with regex patterns for common suffixes.
    """
    if word in SKIP_WORDS_FULL:
        return True
    return bool(_SKIP_COMPARATIVE_RE.match(word))

# Minimal abbreviations skip set (used by context_lock.py and diff_review.py).
SKIP_ABBREVS_MINIMAL: frozenset[str] = frozenset({
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "ANY",
    "CAN", "HAD", "HER", "WAS", "ONE", "OUR", "OUT", "DAY", "GET",
    "HAS", "HIM", "HIS", "HOW", "ITS", "MAY", "NEW", "NOW", "OLD",
    "SEE", "TWO", "WAY", "WHO", "MAN", "MEN",
})

# Full abbreviations skip set (learn.py uses a slightly larger set).
SKIP_ABBREVS_FULL: frozenset[str] = frozenset({
    *SKIP_ABBREVS_MINIMAL,
    "BOY", "DID", "EYE", "MRS",
})


# --- Extraction functions ---

def extract_card_names(text: str, max_length: int = 40) -> Iterator[str]:
    """Extract card names with colons from text.

    Matches patterns like "Geralt: Igni", "Syanna: Duchess".
    """
    for match in CARD_NAME_PATTERN.finditer(text):
        name = match.group(1).strip()
        if len(name) <= max_length:
            yield name


def extract_card_names_no_colon(
    text: str,
    max_words: int = 5,
    min_length: int = 4,
    skip_words: frozenset[str] | None = None,
) -> Iterator[str]:
    """Extract card names WITHOUT colons from text.

    Matches patterns like "Paulie Dahlberg", "Horst Borsodi",
    "Geralt of Rivia", "Filavandrel aén Fidháil".

    Allows function words (of, the, de, van, von, etc.) between
    capitalized words.
    """
    if skip_words is None:
        skip_words = SKIP_WORDS_MINIMAL

    func_pattern = '|'.join(re.escape(w) for w in FUNCTION_WORDS)
    # Match: CapitalizedWord + (space + (function_word | CapitalizedWord)) repeated
    pattern = re.compile(
        rf'\b([A-Z][a-zA-Z]*(?:\s+(?:{func_pattern}|[A-Z][a-zA-Z]*))'
        rf'{{1,{max_words}}})\b'
    )
    for match in pattern.finditer(text):
        name = match.group(1).strip()
        if len(name) >= min_length:
            first = name.split()[0]
            if first not in skip_words:
                yield name


def extract_terms_from_markdown(text: str) -> Iterator[str]:
    """Extract candidate terms from Markdown headers and bold text.

    Markdown headers (## Title) and bold markers (**Name**) often contain
    card names that paragraph scanners miss.
    """
    for line in text.split('\n'):
        stripped = line.strip()

        # Markdown headers
        if stripped.startswith('#'):
            clean = re.sub(r'^#+\s*', '', stripped).strip()
            clean = re.sub(r'\*\*', '', clean).strip()
            for name in extract_card_names(clean):
                yield name
            for name in extract_card_names_no_colon(clean):
                yield name

        # Bold text lines (e.g., "**Paulie Dahlberg (6 → 7)**")
        if '**' in stripped:
            clean = re.sub(r'\*\*', '', stripped).strip()
            for name in extract_card_names(clean):
                yield name
            for name in extract_card_names_no_colon(clean):
                yield name


def extract_capitalized_phrases(
    text: str,
    max_words: int = 3,
    min_length: int = 4,
    skip_words: frozenset[str] | None = None,
) -> Iterator[str]:
    """Extract multi-word capitalized phrases from text.

    Args:
        text: Source text to scan.
        max_words: Maximum number of words in a phrase (default 3).
        min_length: Minimum character length of a phrase (default 4).
        skip_words: Set of words to skip as first word.
    """
    if skip_words is None:
        skip_words = SKIP_WORDS_MINIMAL

    pattern = re.compile(
        rf'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,{max_words}}})\b'
    )
    for match in pattern.finditer(text):
        name = match.group(1).strip()
        if len(name) >= min_length:
            first = name.split()[0]
            if first not in skip_words:
                yield name


def extract_abbreviations(
    text: str,
    skip_abbrevs: frozenset[str] | None = None,
) -> Iterator[str]:
    """Extract all-caps abbreviations from text.

    Args:
        text: Source text to scan.
        skip_abbrevs: Set of abbreviations to skip.
    """
    if skip_abbrevs is None:
        skip_abbrevs = SKIP_ABBREVS_MINIMAL

    for match in ABBREVIATION_PATTERN.finditer(text):
        abbrev = match.group(1)
        if abbrev not in skip_abbrevs:
            yield abbrev


def parse_markdown_table(text: str, min_columns: int = 3) -> list[dict[str, str]]:
    """Parse markdown tables into a list of row dictionaries.

    Headers are normalized to lower-case keys. The special key `_raw` holds
    the original row values in order. Empty rows and header repeats are skipped.

    Args:
        text: Markdown text containing zero or more tables.
        min_columns: Minimum number of columns a data row must have.

    Returns:
        List of row dicts, one per data row across all tables in the text.
    """
    rows: list[dict[str, str]] = []
    headers: list[str] = []
    in_table = False

    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            in_table = False
            headers = []
            continue

        # Escape pipes inside backticks so they don't split columns.
        # Markdown tables allow `\|` to represent a literal pipe; we preserve
        # the escaped form here and let callers unescape if needed.
        ESC = "\x00PIPE\x00"
        safe_line = line
        for quoted in re.findall(r'`[^`]*`', line):
            safe_quoted = quoted.replace("|", ESC)
            safe_line = safe_line.replace(quoted, safe_quoted, 1)

        parts = [p.strip() for p in safe_line.split("|")]
        # Remove leading/trailing empty slots introduced by the outer pipes.
        if parts and not parts[0]:
            parts = parts[1:]
        if parts and not parts[-1]:
            parts = parts[:-1]
        # Restore escaped pipes in each cell.
        parts = [p.replace(ESC, "|") for p in parts]

        if "---" in line:
            in_table = True
            continue

        if not in_table:
            # This is a header row.
            headers = [h.lower().replace(" ", "_") for h in parts]
            continue

        # Data row
        if len(parts) < min_columns:
            continue
        if not any(parts):
            continue
        # Skip repeated header text
        if parts[0].lower() in {"english", "wrong", "forbidden", "abbreviation"}:
            continue

        row: dict[str, str] = {"_raw": "|".join(parts)}
        for idx, value in enumerate(parts):
            if idx < len(headers):
                row[headers[idx]] = value
            else:
                row[f"col_{idx}"] = value
        rows.append(row)

    return rows
