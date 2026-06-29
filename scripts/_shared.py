#!/usr/bin/env python3
"""Shared utilities for gwent-translation-style scripts.

Extracted to eliminate duplication of proper-noun extraction logic
across learn.py, context_lock.py, and diff_review.py.
"""

import re
import sys
from collections.abc import Iterator
from pathlib import Path
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


# --- Translation direction detection ---

# Heuristic thresholds for direction detection (character-ratio based).
# See the caveat in detect_direction's docstring — unreliable on mixed text;
# callers that know the real direction should pass --direction explicitly.
DIRECTION_RATIO = 2        # 中文需明显多于英文（中文字数 > 英文词数 × 此值）
DIRECTION_MIN_TOKENS = 20  # 且达到最小字符/词数才判定，避免短文本误判


def detect_direction(text: str) -> str:
    """Heuristically detect translation direction from output text.

    Returns "encn" when the text reads as a Chinese translation (EN->CN
    output) and "cnen" when it reads as English (CN->EN output). Used by
    the terminology checker, the residue scanner, and the completeness
    guard so all of them agree on which language is the *target* and thus
    which kind of residue to flag.

    Caveat: this is a character-ratio heuristic and is unreliable on
    poorly-translated or heavily mixed text. A CN->EN translation that was
    barely started (still mostly Chinese) is misclassified as "encn", so its
    untranslated Chinese card names go unflagged. Callers that know the real
    direction (the translation workflow always does) should pass it
    explicitly via --direction rather than rely on this fallback.
    """
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    english_words = len(re.findall(r"[A-Za-z]{2,}", text))

    # Substantial Chinese with limited English -> EN->CN output.
    if chinese_chars > english_words * DIRECTION_RATIO and chinese_chars > DIRECTION_MIN_TOKENS:
        return "encn"
    # Substantial English with limited Chinese -> CN->EN output.
    if english_words > chinese_chars / DIRECTION_RATIO and english_words > DIRECTION_MIN_TOKENS:
        return "cnen"
    # Fallback: more Chinese than English -> encn, else cnen.
    return "encn" if chinese_chars >= english_words else "cnen"


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


def extract_cn_variants(lock: dict) -> set[str]:
    """Extract every Chinese variant phrase recorded in a context lock.

    A lock term's ``cn`` field may carry several variants separated by ``/``
    (e.g. ``"蟹蜘蛛领袖/装甲蟹蜘蛛"``). Each variant is a phrase the agent must
    use verbatim, so the check and enforce layers treat them as disambiguating
    context. Centralized here so the two enforcement layers cannot drift apart.
    """
    phrases: set[str] = set()
    for info in lock.get("terms", {}).values():
        cn = info.get("cn", "")
        if not cn:
            continue
        for variant in cn.split("/"):
            variant = variant.strip()
            if variant:
                phrases.add(variant)
    return phrases


def load_lock_file(lock_path: "Path | str") -> dict:
    """Load and parse a context lock JSON file."""
    import json

    return json.loads(Path(lock_path).read_text(encoding="utf-8"))


def build_lock_from_source(source_path: "Path | str") -> Path:
    """Build a context lock from a source file by shelling out to context_lock.py.

    Returns the path to the generated lock file — a temp file the caller is
    responsible for cleaning up. Raises RuntimeError on build failure so callers
    can decide whether to degrade or abort, instead of silently masking errors.
    """
    import subprocess
    import tempfile

    lock_file = Path(tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="gwent_lock_", delete=False
    ).name)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "context_lock.py"),
         "build", str(source_path), "--output", str(lock_file)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        lock_file.unlink(missing_ok=True)
        raise RuntimeError(
            f"context_lock.py build failed: {result.stderr or result.stdout}"
        )
    return lock_file


# Category terms that should NOT be auto-enforced from category_map.md: either
# they collide with an earlier-loaded reference (card_names / keywords_map /
# competitive_terms / terminology_map — first-wins keeps the authoritative CN) or
# they are generic English words whose appearance in prose would cause
# term_missing_or_literal false positives. Everything else in category_map.md is
# Gwent-specific (relict, insectoid, construct, ...) and IS enforced.
SKIP_CATEGORY: frozenset[str] = frozenset({
    # collisions — other references own these
    "leader", "mage", "syndicate", "artifact", "stratagem", "dragon", "siren",
    "cutthroat", "alchemist", "cleric", "witcher", "tactic", "alchemy", "spell",
    "berserk", "berserker", "soldier", "machine", "knight", "bandit", "cultist",
    "druid", "pirate", "warrior", "hunter", "archer",
    # generic common words — false-positive risk (appear in non-category prose)
    "human", "agent", "support", "officer", "aristocrat", "scholar", "thief",
    "story", "location", "blind", "organic",
    "spirit", "beast", "cursed", "dryad", "ogre", "mutant", "devourer",
    "specter",  # same CN as spirit (鬼灵), rare in prose
})


# --- Unified Term Authority ---


class TermAuthority:
    """Unified resolver for Gwent terms, card names, aliases, and abbreviations.

    Loads all reference files under `references/` and provides a single lookup
    interface. This is the source-of-truth layer used by `context_lock.py`,
    `auto_pipeline.py`, `term_enforcer.py`, and other scripts.

    The authority is read-only: it never writes to reference files. It resolves
    English terms, Chinese terms, aliases, abbreviations, and misspellings to
    their canonical English + Chinese pair.
    """

    def __init__(self, ref_dir: "Path | str | None" = None) -> None:
        if ref_dir is None:
            ref_dir = Path(__file__).parent.parent / "references"
        self.ref_dir = Path(ref_dir)

        # canonical_en_lower -> entry dict
        self._entries: dict[str, dict] = {}
        # cn -> entry dict (multiple CN may map to same EN; first wins)
        self._cn_entries: dict[str, dict] = {}
        # alias/abbreviation -> canonical_en_lower
        self._alias_to_en: dict[str, str] = {}
        self._abbrev_to_en: dict[str, str] = {}
        # wrong_cn -> correct_cn (from renamed/corrected and fuzzy fixes)
        self._cn_corrections: dict[str, str] = {}
        # base name lower -> list of variant dicts
        self._ambiguous: dict[str, list[dict]] = {}
        # en_lower -> canonical_en for enforced category terms (relict, insectoid, ...)
        # Scanned separately: category words usually appear lowercase in prose and
        # the capitalized-phrase extractor would miss them.
        self._categories: dict[str, str] = {}
        # en_lower -> canonical_en for distinctive faction names (Nilfgaard, Skellige,
        # ...). Single capitalized words are missed by the capitalized-phrase
        # extractor, so distinctive faction names are scanned directly. Generic
        # faction words (Monsters, Neutral) are excluded to avoid false positives
        # and rely on their abbreviations (MO, NE) instead.
        self._factions: dict[str, str] = {}
        # en_lower -> {en, cn_name, cn_ability, card_id}: official effect text,
        # loaded from effect_text.json (built by build_effect_reference.py).
        # Used to inject the official CN ability so the agent copies it verbatim
        # when quoting a card's effect (term-enforcer can't lock long sentences).
        self._effects: dict[str, dict] = {}

        self._loaded = False
        self._load_all()

    def _load_all(self) -> None:
        if self._loaded:
            return
        self._load_card_names()
        self._load_terminology_map()
        self._load_reverse_terminology_map()
        self._load_competitive_terms()
        self._load_keywords_map()
        self._load_category_map()
        self._load_card_attributes_map()
        self._load_ambiguous_names()
        self._load_cn_fuzzy_fixes()
        self._load_correction_guide()
        self._load_effect_text()
        self._loaded = True

    # -- registration helpers --

    def _register(
        self,
        en: str,
        cn: str,
        source: str,
        term_type: str,
        aliases: list[str] | None = None,
        abbrevs: list[str] | None = None,
    ) -> None:
        """Register a canonical EN <-> CN mapping."""
        en = en.strip()
        cn = cn.strip()
        if not en or not cn:
            return

        en_lower = en.lower()
        entry = self._entries.get(en_lower)
        if entry is None:
            entry = {
                "canonical_en": en,
                "cn": cn,
                "source": source,
                "type": term_type,
                "aliases": list(aliases or []),
                "abbrevs": list(abbrevs or []),
            }
            self._entries[en_lower] = entry
        else:
            # Same canonical EN seen again; merge aliases/abbrevs, prefer earlier CN.
            for alias in aliases or []:
                if alias not in entry["aliases"]:
                    entry["aliases"].append(alias)
            for abbrev in abbrevs or []:
                if abbrev not in entry["abbrevs"]:
                    entry["abbrevs"].append(abbrev)

        if cn not in self._cn_entries:
            self._cn_entries[cn] = entry

        for alias in aliases or []:
            self._add_alias(alias, en)
        for abbrev in abbrevs or []:
            self._add_abbrev(abbrev, en)

    def _add_alias(self, alias: str, canonical_en: str) -> None:
        alias = alias.strip().lower()
        canonical = canonical_en.strip().lower()
        if alias and canonical and alias != canonical:
            self._alias_to_en[alias] = canonical

    def _add_abbrev(self, abbrev: str, canonical_en: str) -> None:
        abbrev = abbrev.strip().upper()
        canonical = canonical_en.strip().lower()
        if abbrev and canonical:
            self._abbrev_to_en[abbrev] = canonical

    def _add_cn_correction(self, wrong: str, correct: str) -> None:
        wrong = wrong.strip()
        correct = correct.strip()
        if wrong and correct and wrong != correct:
            self._cn_corrections[wrong] = correct

    # -- reference loaders --

    def _load_card_names(self) -> None:
        path = self.ref_dir / "card_names.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=3)

        # Verified cards and leaders share similar schemas.
        for row in rows:
            en = row.get("english", "").strip()
            cn = row.get("chinese", "").strip()
            if not en or not cn or en.lower() == "english":
                continue
            self._register(en, cn, "card_names.md", "card")

        # Leader aliases: Alias | Maps To | Notes
        # We map alias -> canonical EN, then copy canonical's CN.
        in_aliases = False
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("## Leader Aliases"):
                in_aliases = True
                continue
            if in_aliases and line.startswith("## "):
                break
            if not in_aliases:
                continue
            if not line.startswith("|") or "---" in line or "Alias" in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            # Remove leading/trailing empty slots introduced by outer pipes.
            if parts and not parts[0]:
                parts = parts[1:]
            if parts and not parts[-1]:
                parts = parts[:-1]
            if len(parts) < 3:
                continue
            alias, maps_to = parts[0], parts[1]
            if not alias or not maps_to:
                continue
            maps_to_lower = maps_to.lower()
            if maps_to_lower in self._entries:
                entry = self._entries[maps_to_lower]
                self._register(
                    maps_to,
                    entry["cn"],
                    "card_names.md",
                    "leader_alias",
                    aliases=[alias],
                )
            else:
                # Alias points to an EN not in the verified list; register alias as EN.
                self._register(alias, maps_to, "card_names.md", "leader_alias")

        # Renamed / Corrected: Skill原版 | 修正后 | 说明
        in_renamed = False
        for line in text.split("\n"):
            line = line.strip()
            if "Renamed / Corrected" in line:
                in_renamed = True
                continue
            if in_renamed and line.startswith("## "):
                break
            if not in_renamed:
                continue
            if not line.startswith("|") or "---" in line or "Skill原版" in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            # Remove leading/trailing empty slots introduced by outer pipes.
            if parts and not parts[0]:
                parts = parts[1:]
            if parts and not parts[-1]:
                parts = parts[:-1]
            if len(parts) < 3:
                continue
            wrong, correct = parts[0], parts[1]
            self._add_cn_correction(wrong, correct)

    def _load_terminology_map(self) -> None:
        path = self.ref_dir / "terminology_map.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=2)

        for row in rows:
            # Columns vary: "English | Chinese | Notes" or "Forbidden | Must Use | Example"
            en = row.get("english", "").strip() or row.get("forbidden", "").strip()
            cn = row.get("chinese", "").strip() or row.get("must_use", "").strip()
            if not en or not cn or en.lower() in ("english", "forbidden"):
                continue
            self._register(en, cn, "terminology_map.md", "terminology")

    def _load_reverse_terminology_map(self) -> None:
        path = self.ref_dir / "reverse_terminology_map.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=2)

        for row in rows:
            cn = row.get("chinese", "").strip()
            en = row.get("english", "").strip()
            if not cn or not en or cn.lower() == "chinese":
                continue
            self._register(en, cn, "reverse_terminology_map.md", "terminology")

    def _load_competitive_terms(self) -> None:
        path = self.ref_dir / "competitive_terms.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=2)

        for row in rows:
            en = row.get("english", "").strip() or row.get("english_deck_name", "").strip()
            cn = row.get("chinese", "").strip() or row.get("community_chinese", "").strip()
            abbrev = row.get("abbreviations", "").strip()
            if not en or not cn or en.lower() == "english":
                continue

            abbrevs: list[str] = []
            aliases: list[str] = []
            if abbrev:
                for a in abbrev.split(","):
                    a = a.strip()
                    if a:
                        abbrevs.append(a)

            # Community deck names section may use "English Deck Name" -> "Community Chinese".
            term_type = "competitive"
            if row.get("english_deck_name"):
                term_type = "deck_name"

            self._register(en, cn, "competitive_terms.md", term_type, aliases=aliases, abbrevs=abbrevs)

    def _load_keywords_map(self) -> None:
        path = self.ref_dir / "keywords_map.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=2)

        for row in rows:
            en = row.get("english", "").strip()
            cn = row.get("chinese", "").strip()
            if not en or not cn or en.lower() == "english":
                continue
            self._register(en, cn, "keywords_map.md", "keyword")

    def _load_category_map(self) -> None:
        """Load card category terms (relict / insectoid / construct / ...).

        Loaded AFTER keywords_map / competitive_terms / terminology_map so that
        collisions (leader, mage, syndicate, ...) keep the authoritative CN from
        those files via first-wins. Generic / colliding English words are skipped
        (SKIP_CATEGORY); the remaining Gwent-specific categories are registered AND
        recorded in self._categories so get_all_for_text can scan for them in
        lowercase prose (the capitalized-phrase extractor misses them).
        """
        path = self.ref_dir / "category_map.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=3)
        for row in rows:
            en = row.get("english", "").strip()
            cn = row.get("chinese", "").strip()
            if not en or en.lower() == "english":
                continue
            # category_map uses "—" for unmapped CN; _register would otherwise
            # store the em-dash as a real CN and the enforcer would match it.
            if not cn or cn in {"—", "－", "-"}:
                continue
            if en.lower() in SKIP_CATEGORY:
                continue
            self._register(en, cn, "category_map.md", "category")
            self._categories[en.lower()] = en

    def _load_card_attributes_map(self) -> None:
        """Load rarity + faction (name & abbreviation) terms.

        Factions collide with terminology_map / reverse_terminology_map names, so
        this loads AFTER them: first-wins keeps the authoritative faction CN, while
        the abbreviations (NR/MO/SK/ST/SY/NE) are still attached via _add_abbrev.
        Neutral/中立 is new (no collision) so it registers fresh. Rarity words are
        generic English: registered, but they only enforce when capitalized in the
        source (no lowercase scan) to avoid false positives.
        """
        path = self.ref_dir / "card_attributes_map.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=2)
        for row in rows:
            en = row.get("english", "").strip()
            cn = row.get("chinese", "").strip()
            if not en or not cn or en.lower() == "english":
                continue
            abbr = row.get("abbreviation", "").strip()
            if abbr and abbr.lower() != "abbreviation":
                self._register(en, cn, "card_attributes_map.md", "faction",
                               abbrevs=[abbr])
                # Distinctive single-word faction names are scanned in prose too;
                # generic ones (monsters/neutral) rely on their abbreviation only.
                if en.lower() not in {"monsters", "neutral"}:
                    self._factions[en.lower()] = en
            else:
                self._register(en, cn, "card_attributes_map.md", "rarity")

    def _load_ambiguous_names(self) -> None:
        path = self.ref_dir / "ambiguous_names.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        current_base_en: str | None = None

        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("## "):
                # Header format: "## 杰洛特 (Geralt) — 6 versions"
                match = re.search(r"\(([A-Za-z][A-Za-z\s':]*)\)", line)
                if match:
                    current_base_en = match.group(1).strip()
                continue

            if not line.startswith("|") or "---" in line or "Full Name" in line:
                continue
            if current_base_en is None:
                continue

            parts = [p.strip() for p in line.split("|")]
            # Remove leading/trailing empty slots introduced by outer pipes.
            if parts and not parts[0]:
                parts = parts[1:]
            if parts and not parts[-1]:
                parts = parts[:-1]
            if len(parts) < 3:
                continue
            full_en, cn = parts[0], parts[1]
            if not full_en or not cn or full_en.lower() == "full name":
                continue

            base_lower = current_base_en.lower()
            variant = {"en": full_en, "cn": cn}
            self._ambiguous.setdefault(base_lower, []).append(variant)

            # Also register the full name as a canonical card if not already present.
            self._register(full_en, cn, "ambiguous_names.md", "card")

    def _load_cn_fuzzy_fixes(self) -> None:
        path = self.ref_dir / "cn_fuzzy_fixes.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=2)

        for row in rows:
            wrong = row.get("wrong", "").strip()
            correct = row.get("correct", "").strip()
            if not wrong or not correct or wrong.lower() == "wrong":
                continue
            self._add_cn_correction(wrong, correct)
            # If correct is a known CN, register wrong-CN as alias for the EN.
            if correct in self._cn_entries:
                entry = self._cn_entries[correct]
                self._add_alias(wrong, entry["canonical_en"])

    def _load_correction_guide(self) -> None:
        path = self.ref_dir / "correction_guide.md"
        if not path.exists():
            return

        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=2)

        for row in rows:
            wrong = row.get("wrong", "").strip()
            right = row.get("right", "").strip()
            if not wrong or not right or wrong.lower() == "wrong":
                continue
            # Correction guide Section 1 is EN wrong -> EN right; others may be mixed.
            # We treat "right" as canonical EN if it maps to a known CN; otherwise store as alias.
            right_lower = right.lower()
            if right_lower in self._entries:
                entry = self._entries[right_lower]
                self._register(
                    right,
                    entry["cn"],
                    "correction_guide.md",
                    "terminology",
                    aliases=[wrong],
                )
            else:
                self._add_alias(wrong, right)

    def _load_effect_text(self) -> None:
        """Load official card effect text (EN + CN) from effect_text.json.

        Built by build_effect_reference.py from the card-data SSOT. Holds the
        official CN ability per card so the translation pipeline can inject it
        for the agent to copy verbatim when quoting effects. Degrades to empty
        (no injection) if the file is missing; on a parse/encoding error it
        degrades to empty AND warns on stderr so the failure is not silent.
        health_check also validates parseability independently.
        """
        path = self.ref_dir / "effect_text.json"
        if not path.exists():
            return
        try:
            import json
            self._effects = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            # A truncated/corrupt file would silently disable effect injection
            # across the whole pipeline — surface it instead of hiding it.
            print(f"[WARN] effect_text.json failed to parse ({exc}); "
                  f"effect injection disabled.", file=sys.stderr)
            self._effects = {}

    # -- public API --

    def resolve(self, term: str) -> dict | None:
        """Resolve any term (EN, CN, alias, abbreviation) to canonical info.

        Returns a dict with keys:
            canonical_en: str
            cn: str
            source: str
            type: str
            aliases: list[str]
            abbrevs: list[str]
            variants: list[dict]  # only populated for ambiguous base names
            match_type: str       # exact, alias, abbreviation, cn_exact, cn_correction, ambiguous_base
        """
        if not term or not term.strip():
            return None

        original = term.strip()
        key = original.lower()

        # Direct English match.
        if key in self._entries:
            return self._make_result(self._entries[key], "exact")

        # Alias -> English.
        if key in self._alias_to_en:
            canonical_key = self._alias_to_en[key]
            if canonical_key in self._entries:
                return self._make_result(self._entries[canonical_key], "alias")

        # Abbreviation -> English.
        upper = original.upper()
        if upper in self._abbrev_to_en:
            canonical_key = self._abbrev_to_en[upper]
            if canonical_key in self._entries:
                return self._make_result(self._entries[canonical_key], "abbreviation")

        # Direct Chinese match.
        if original in self._cn_entries:
            return self._make_result(self._cn_entries[original], "cn_exact")

        # Chinese correction.
        if original in self._cn_corrections:
            corrected = self._cn_corrections[original]
            if corrected in self._cn_entries:
                return self._make_result(self._cn_entries[corrected], "cn_correction")

        # Ambiguous base name.
        if key in self._ambiguous:
            return {
                "canonical_en": original,
                "cn": "",
                "source": "ambiguous_names.md",
                "type": "ambiguous",
                "aliases": [],
                "abbrevs": [],
                "variants": list(self._ambiguous[key]),
                "match_type": "ambiguous_base",
            }

        return None

    def _make_result(self, entry: dict, match_type: str) -> dict:
        return {
            "canonical_en": entry["canonical_en"],
            "cn": entry["cn"],
            "source": entry["source"],
            "type": entry["type"],
            "aliases": list(entry.get("aliases", [])),
            "abbrevs": list(entry.get("abbrevs", [])),
            "variants": [],
            "match_type": match_type,
        }

    def get_official_ability(self, en_name: str) -> dict | None:
        """Return the official effect record for a card by English name, or None.

        Record: {en, cn_name, cn_ability, card_id}. cn_ability is the official
        Chinese ability text the agent should copy verbatim when quoting the
        card's effect.
        """
        if not en_name:
            return None
        return self._effects.get(en_name.strip().lower())

    def get_all_for_text(self, text: str) -> list[dict]:
        """Extract and resolve all known terms from a source text."""
        candidates: set[str] = set()
        for name in extract_card_names(text):
            candidates.add(name.strip())
        for name in extract_card_names_no_colon(text, max_words=5, min_length=4):
            candidates.add(name.strip())
        for name in extract_terms_from_markdown(text):
            candidates.add(name.strip())
        for name in extract_capitalized_phrases(text, max_words=3, min_length=4):
            candidates.add(name.strip())
        for abbrev in extract_abbreviations(text):
            candidates.add(abbrev.strip())

        # Single-word ambiguous base names (e.g. "Geralt", "Regis") are not caught
        # by the regex extractors above. Scan for them directly.
        text_lower = text.lower()
        for base_lower, variants in self._ambiguous.items():
            # Match as a whole word to avoid false positives.
            if re.search(rf"\b{re.escape(base_lower)}\b", text_lower):
                candidates.add(base_lower.title() if base_lower else base_lower)

        # Category terms (relict, insectoid, ...) usually appear lowercase in
        # prose ("GN relicts", "vampire deck") and are missed by the capitalized
        # extractors above. Scan them directly, tolerating a trailing plural -s.
        for cat_lower, canonical_en in self._categories.items():
            if re.search(rf"\b{re.escape(cat_lower)}s?\b", text_lower):
                candidates.add(canonical_en)

        # Distinctive faction names (Nilfgaard, Skellige, Scoia'tael, Syndicate,
        # Northern Realms) — single capitalized words missed by the phrase
        # extractor. Plain word match (faction names are not pluralized).
        for fac_lower, canonical_en in self._factions.items():
            if re.search(rf"\b{re.escape(fac_lower)}\b", text_lower):
                candidates.add(canonical_en)

        # Sort by length descending so full names are resolved before abbreviations.
        candidates = sorted(candidates, key=lambda x: (-len(x), x.lower()))

        results: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for cand in candidates:
            resolved = self.resolve(cand)
            if not resolved:
                continue
            seen_key = (resolved["canonical_en"].lower(), resolved["cn"])
            if seen_key in seen:
                continue
            seen.add(seen_key)
            results.append({"term": cand, **resolved})

        return results

    def get_canonical(self, term: str) -> str | None:
        """Return canonical EN for a term, or None if unknown."""
        resolved = self.resolve(term)
        return resolved["canonical_en"] if resolved else None

    def get_cn(self, term: str) -> str | None:
        """Return official Chinese for a term, or None if unknown/ambiguous."""
        resolved = self.resolve(term)
        return resolved["cn"] if resolved else None


# Cached module-level instance for scripts that need repeated lookups.
_term_authority_cache: dict[str, TermAuthority] = {}


def get_term_authority(ref_dir: "Path | str | None" = None) -> TermAuthority:
    """Return a cached TermAuthority instance for the given references directory."""
    key = str(ref_dir) if ref_dir else "default"
    if key not in _term_authority_cache:
        _term_authority_cache[key] = TermAuthority(ref_dir)
    return _term_authority_cache[key]
