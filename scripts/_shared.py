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


def source_is_chinese(text: str) -> bool:
    """True when the text reads predominantly Chinese — i.e. a CN->EN source.

    detect_direction reports the language a text reads as the TARGET of a
    translation; applied to a SOURCE file, "encn" (Chinese target) means the
    source itself is Chinese. We invert that label to name the SOURCE language
    for extraction-strategy selection, reusing detect_direction's thresholds so
    the extractor and the checker can never disagree on what counts as Chinese.
    """
    return detect_direction(text) == "encn"


# --- --verbose-terms output sizing ---

# Default cap for term/violation lists in --json output. Without --verbose-terms a
# report emits COUNTS plus this many entries (top N); with --verbose-terms it emits
# the full list. Keeps a card-heavy article from flooding agent context.
TERMS_SUMMARY_TOP_N = 5


def terms_summary(items, verbose: bool, n: int = TERMS_SUMMARY_TOP_N):
    """Return the full list when ``verbose`` else the first ``n`` items.

    Callers still report the true total count separately, so the default mode is
    "counts + top N" and ``--verbose-terms`` switches to the complete list.
    """
    return list(items) if verbose else list(items)[:n]


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


# --- Aggressive card-variant matching -------------------------------------
# Catch-all layer for source-text card-name VARIANTS the strict regex
# extractors miss: "Double-Bladed Dagur" -> Dagur Two Blades (reverse
# containment), "Geraltt of Rivia" -> Geralt of Rivia (edit distance),
# "Schirru" -> Schirrú (accent-insensitive). Applied AFTER the strict
# extractors in get_all_for_text so exact matches keep their fast path.

CARD_VARIANT_MIN_TOKEN = 4   # reverse-containment: source-token min length (chars)
CARD_FUZZY_MAX_EDIT = 2      # normalized Levenshtein threshold for a fuzzy match (long tokens)
CARD_FUZZY_MIN_TOKEN = 5     # edit-distance source-token min length (short = noisy)
# Short tokens use a TIGHTER edit-distance threshold so a 6-char game keyword
# cannot fuzzy-lock an unrelated card 2 edits away (Deploy -> Decoy). Real
# single-char typos (Geraltt -> Geralt, 7 chars) and accent / reverse-containment
# variants (Schirru, Dagur, Froth) are unaffected.
CARD_FUZZY_SHORT_MAXLEN = 6
CARD_FUZZY_SHORT_MAX_EDIT = 1

# High-frequency game verbs / mechanics words that are NEVER card names but
# fuzzy- or substring-match one (Deploy -> Decoy, Boost -> 布荷特). Excluded from
# aggressive card matching outright; they belong to the keyword/terminology layer.
# (self._game_terms is the authoritative dynamic check; this set covers common
# verbs that may be typed as competitive/other and so absent from _game_terms.)
AGGRESSIVE_SKIP_GAME_WORDS: frozenset[str] = frozenset({
    "deploy", "deployed", "play", "played", "draw", "draws", "summon", "summoned",
    "bleed", "bleeding", "boost", "boosted", "order", "ordered", "armor",
    "cost", "buff", "buffed", "nerf", "nerfed", "discard", "banish", "heal",
    "damage", "lock", "locked", "reveal", "revealed", "spawn", "transform",
    "destroy", "purify", "poison", "shield",
})

# Common English nouns/adjectives that complete exactly one card name and so
# would be false-positive reverse-containment hits (Baron->Bloody Baron,
# Rain->Torrential Rain, Justice->Novigradian Justice). Proper card nouns
# (Donimir, Erland, Froth, Dagur) are NOT here. Grows as new collisions surface.
CARD_VARIANT_COMMON_WORDS: frozenset[str] = frozenset({
    "armor", "aristocrats", "baron", "books", "boost", "cache", "cave", "combat",
    "compass", "cost", "covenant", "decision", "dormant", "formation", "gale",
    "gift", "glory", "golem", "jackal", "justice", "knight", "lady", "larva",
    "lined", "muscle", "order", "poet", "rain", "scroll", "season", "seductress",
    "senior", "sentinel", "shadows", "stations", "steel", "sunset",
    "tainted", "thug", "wanderers", "zeal",
    # common fantasy/game nouns that also complete card names
    "blood", "fire", "storm", "gold", "wind", "death", "dream", "vision",
    "curse", "blessing", "rite", "ritual", "oath", "vow", "tome", "blade",
    "spear", "helm", "gem", "bone", "ash", "mist", "frost", "flame",
    "tomb", "tower", "gate", "bridge", "master", "guard", "warrior",
    "soldier", "hunter", "scout", "priest", "beast", "dragon", "wolf",
    "bear", "tree", "stone", "silver",
})

# Single capitalized token (Latin accents / apostrophes / hyphens OK).
_VARIANT_TOKEN_RE = re.compile(r"[A-Z][A-Za-zÀ-ÿ'’\-]*")


def _fold_ascii(s: str) -> str:
    """Lowercase + NFKD accent-fold + drop non-alphanumerics.

    Accent/typo-insensitive comparison key: "Schirrú" and "Schirru" both fold to
    "schirru"; "Geralt of Rivia" folds to "geraltofrivia".
    """
    import unicodedata
    s = unicodedata.normalize("NFKD", s).lower()
    return re.sub(r"[^a-z0-9]", "", s)


def _edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance (pure stdlib, two-row DP)."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    lb = len(b)
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1,
                         prev[j - 1] + (0 if ca == b[j - 1] else 1))
        prev = cur
    return prev[lb]


_card_variant_index_cache: dict[str, dict] = {}


def _card_variant_index(ref_dir: "Path | str") -> dict:
    """Build + cache a folded card-name lookup index for aggressive matching.

      norm_to_display: folded-name -> canonical EN display (accent-insensitive exact)
      word_to_norms:   folded single word -> set of folded canonical names
                       (reverse-containment: source token ⊂ canonical name)
      by_len:          folded-length -> list of folded canonical names
                       (length-windowed edit distance)
    Cards-only (from get_card_names_index) so common terms never participate.
    """
    key = str(ref_dir)
    cached = _card_variant_index_cache.get(key)
    if cached is not None:
        return cached
    en_index = get_card_names_index(ref_dir)  # en_lower -> (display_en, cn)
    norm_to_display: dict[str, str] = {}
    word_to_norms: dict[str, set[str]] = {}
    by_len: dict[int, list[str]] = {}
    for display in (v[0] for v in en_index.values()):
        n = _fold_ascii(display)
        if not n:
            continue
        norm_to_display.setdefault(n, display)
        by_len.setdefault(len(n), []).append(n)
        # Split the display name into words BEFORE folding (folding drops the
        # spaces, which would fuse multi-word names into one blob) so each word
        # keys reverse-containment (Dagur -> Dagur Two Blades).
        for w in re.split(r"[\s\-:;,/'’]+", display.lower()):
            fw = _fold_ascii(w)
            if fw:
                word_to_norms.setdefault(fw, set()).add(n)
    idx = {"norm_to_display": norm_to_display,
           "word_to_norms": word_to_norms,
           "by_len": by_len}
    _card_variant_index_cache[key] = idx
    return idx


def _best_fuzzy(norm: str, by_len: dict[int, list[str]], max_edit: int = CARD_FUZZY_MAX_EDIT) -> str | None:
    """Return the folded canonical name within `max_edit` of `norm`
    (min distance; None if none qualifies). Length-windowed to bound the scan.

    Callers pass a tighter `max_edit` for short tokens (see CARD_FUZZY_SHORT_*),
    so a 6-char game keyword cannot fuzzy-lock an unrelated card 2 edits away."""
    L = len(norm)
    best_d = max_edit + 1
    best: str | None = None
    for cl in range(max(1, L - max_edit), L + max_edit + 1):
        for cand in by_len.get(cl, ()):
            if cand == norm:
                continue
            d = _edit_distance(norm, cand)
            if d < best_d:
                best_d, best = d, cand
    return best

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
        # en_lower -> {english, intended_cn, literal_forbidden, note}: community
        # slang/jargon loaded from slang_map.md. NOT registered as enforced terms
        # (slang is register guidance, not a hard lock). Used by auto_pipeline pre
        # (slang_hints injection) and check_translation (reverse-scan warn).
        self._slang: dict[str, dict] = {}
        # CN -> [canonical_en, ...]: reverse index for the CN->EN source
        # extractor (get_all_for_text_cn). Unlike _cn_entries (first-wins) this
        # keeps EVERY English candidate, so a CN name shared by several cards
        # (e.g. 迪门家族水手 -> Dimun Pirate AND Dimun Corsair) surfaces as a
        # collision. Only en values that START with an ASCII letter are kept, so
        # correction rows whose "english" field is itself Chinese
        # (出场率 -> 登场率) never pollute the CN->EN lock.
        self._cn_to_ens: dict[str, list[str]] = {}
        # en_lower -> canonical_en for keyword / terminology / competitive /
        # deck_name terms. Scanned directly in get_all_for_text (EN->CN source)
        # because these single-word game terms (deploy, provision, order, Meta, ...)
        # appear lowercase in prose and are missed by the capitalized card-name
        # extractors — without this the EN->CN lock drops them, an asymmetry vs the
        # CN->EN dictionary lookup (which already catches them via _cn_to_ens).
        self._game_terms: dict[str, str] = {}

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
        self._load_slang_map()
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

        # Feed the multi-candidate CN->EN index used by CN-source extraction.
        if cn and re.match(r"[A-Za-z]", en):
            lst = self._cn_to_ens.setdefault(cn, [])
            if en not in lst:
                lst.append(en)
        # Track core game-mechanic terms (keywords / terminology) for the EN->CN
        # direct scan in get_all_for_text. Competitive terms and deck names are
        # excluded: they are looser meta vocabulary / long multi-word phrases that
        # are already caught by the capitalized card-name extractors, and
        # force-locking them (then requiring their exact CN) would over-flag
        # legitimately paraphrased translations.
        if term_type in ("keyword", "terminology"):
            self._game_terms.setdefault(en_lower, en)

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
        # Main card data: the build-time 4-language table (card_names_4lang.json,
        # generated by build_card_names_reference.py from the official gwent.one
        # mirror). Supersedes the old hand-maintained card_names.md main table
        # (~1260 cards) with the full official set (1381 cards). EN drives
        # registration; CN is attached so resolve() can look up either direction.
        path = self.ref_dir / "card_names_4lang.json"
        if path.exists():
            import json
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                data = {}
            for rec in data.values():
                en = (rec.get("en") or "").strip()
                cn = (rec.get("cn") or "").strip()
                if en and cn:
                    self._register(en, cn, "card_names_4lang.json", "card")

        # Manual overrides (aliases / renamed / direct EN->CN). Applied AFTER the
        # 4lang table so leader-alias canonicals are already registered; direct
        # Overrides force-win over the 4lang CN.
        self._load_card_overrides()

    def _load_card_overrides(self) -> None:
        """Load hand-maintained card overrides from card_overrides.md.

        Three section types (manual override wins over the 4lang table on
        conflict):
          ## Overrides        (English | Chinese | Notes)   direct EN->CN, force-win
          ## Leader Aliases   (Alias | Maps To | Notes)     EN alias -> canonical EN
          ## Renamed/Corrected (Skill原版 | 修正后 | 说明)   CN wrong -> correct

        Parsed via the shared module-level _parse_card_overrides so this resolver
        and the card-index helpers (get_card_names_index etc.) cannot drift apart.
        """
        parsed = _parse_card_overrides(self.ref_dir / "card_overrides.md")

        # Direct EN->CN overrides: force-win over the 4lang registration.
        for en, cn in parsed["overrides"]:
            self._force_card_override(en, cn)

        # Leader aliases: alias resolves to the canonical card (already registered
        # from the 4lang table). Copy the canonical's CN so the alias locks to it.
        for alias, maps_to in parsed["aliases"]:
            canonical = self._entries.get(maps_to.strip().lower())
            if canonical:
                self._register(
                    canonical["canonical_en"], canonical["cn"],
                    "card_overrides.md", "leader_alias", aliases=[alias],
                )
            else:
                # Canonical not registered (e.g. 4lang table missing) — record the
                # alias pointing at the EN literal so it is at least resolvable.
                self._register(alias, maps_to, "card_overrides.md", "leader_alias")

        # CN corrections (wrong -> correct): soft alias layer, additive.
        for wrong, correct in parsed["renamed"].items():
            self._add_cn_correction(wrong, correct)

    def _force_card_override(self, en: str, cn: str) -> None:
        """Register an EN->CN card mapping that WINS over an existing entry.

        Unlike _register (first-wins), this overwrites the CN of an existing card
        so a manual override in card_overrides.md takes precedence over the
        generated 4lang table. Also fixes the reverse (_cn_entries) index.
        """
        en = en.strip()
        cn = cn.strip()
        if not en or not cn:
            return
        en_lower = en.lower()
        entry = self._entries.get(en_lower)
        if entry is None:
            self._register(en, cn, "card_overrides.md", "card")
            return
        old_cn = entry.get("cn", "")
        if old_cn and old_cn != cn:
            # Drop the stale reverse mapping so resolve(cn) cannot double-resolve.
            if self._cn_entries.get(old_cn) is entry:
                del self._cn_entries[old_cn]
        entry["cn"] = cn
        entry["source"] = "card_overrides.md"
        if cn not in self._cn_entries:
            self._cn_entries[cn] = entry
        # Mirror the forced CN swap into the multi-candidate CN->EN index.
        if re.match(r"[A-Za-z]", en):
            lst = self._cn_to_ens.setdefault(cn, [])
            if en not in lst:
                lst.append(en)
            if old_cn and old_cn != cn:
                stale = self._cn_to_ens.get(old_cn)
                if stale and en in stale:
                    stale.remove(en)
                    if not stale:
                        del self._cn_to_ens[old_cn]

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
                # competitive_terms.md 缩写列实际用分号分隔（如 "Porv; cost; p"），
                # 同时兼容逗号，避免 TermAuthority 与 check_translation 解析漂移。
                for a in re.split(r"[;,]", abbrev):
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

    def _load_slang_map(self) -> None:
        """Load community slang/jargon from slang_map.md.

        Slang is register guidance, NOT an enforced term: deliberately kept out of
        the _register lock (slang depends on tone; hard-locking it would break the
        hard-layer card-info / soft-layer rhetoric split). Stored in self._slang
        for auto_pipeline pre (slang_hints injection) and check_translation
        (reverse-scan warn).
        """
        path = self.ref_dir / "slang_map.md"
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=3)
        for row in rows:
            en = row.get("english", "").strip()
            intended = row.get("intended_cn", "").strip()
            if not en or en.lower() == "english" or not intended:
                continue
            self._slang[en.lower()] = {
                "english": en,
                "intended_cn": intended,
                "literal_forbidden": row.get("literal_forbidden", "").strip(),
                "note": row.get("note", "").strip(),
            }
            # Surface slang CN in the CN->EN extraction index too: a CN source
            # using 加强版 should lock to "on steroids". intended_cn may carry
            # "/"-separated community variants; register each (>=2 chars).
            if re.match(r"[A-Za-z]", en):
                for variant in re.split(r"/", intended):
                    variant = variant.strip()
                    if variant and len(variant) >= 2:
                        lst = self._cn_to_ens.setdefault(variant, [])
                        if en not in lst:
                            lst.append(en)

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
        # NOTE: this resolver intentionally ignores the "✓" Type-column marker that
        # check_translation.load_fuzzy_fixes uses to skip "actually correct" rows.
        # Here every wrong->correct pair is registered as a soft alias/correction,
        # which is desired (e.g. 迪迦 resolves to 辛迪加/Syndicate for lookups). If you
        # add a ✓-marked row expecting BOTH consumers to skip it, update this method.
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

    def _aggressive_card_matches(
        self, text: str, unresolved: list[str] | None = None,
    ) -> list[tuple[str, str]]:
        """Aggressive deterministic matching for card-name VARIANTS the strict
        regex extractors miss. Returns list of (canonical_en_display, variant)
        pairs for get_all_for_text to resolve exactly and lock.

        Order: accent-insensitive exact -> reverse containment -> edit distance.
        All paths guarded against common-word false positives (token ≥
        CARD_VARIANT_MIN_TOKEN, Capitalized/ALLCAPS, not is_likely_common_word).

          text:       source text (scanned for single capitalized words)
          unresolved: candidates the strict extractors produced but resolve()
                      rejected (phrases like "Geraltt of Rivia"); fed to edit
                      distance so the robust phrase extractor is reused.
        """
        idx = _card_variant_index(self.ref_dir)
        norm_to_display = idx["norm_to_display"]
        word_to_norms = idx["word_to_norms"]
        by_len = idx["by_len"]

        # Words that appear in LOWERCASE in the text. A proper-noun card name
        # (Donimir, Erland, Froth) is always capitalized; a common English word
        # that only coincidentally completes one card name (baron, rain, season)
        # virtually also appears lowercase in prose. Used to keep reverse
        # containment from locking generic words.
        lowercase_words = {_fold_ascii(w) for w in re.findall(r"\b[a-z][a-z]+\b", text)}

        results: list[tuple[str, str]] = []
        seen_canon: set[str] = set()

        def _emit(norm_canon: str, variant: str) -> None:
            display = norm_to_display.get(norm_canon)
            if display and norm_canon not in seen_canon:
                seen_canon.add(norm_canon)
                results.append((display, variant))

        def _word_ok(norm: str, span: str) -> bool:
            if len(_fold_ascii(span)) < CARD_VARIANT_MIN_TOKEN:
                return False
            # Common-word guard applies to the FUZZY path too (not only reverse
            # containment): otherwise Boost / Baron / Armor still fuzzy-lock a card.
            return not (is_likely_common_word(span)
                        or is_likely_common_word(span.title())
                        or norm in CARD_VARIANT_COMMON_WORDS)

        # 1. Single capitalized words from the text.
        for span in {m.group(0) for m in _VARIANT_TOKEN_RE.finditer(text)}:
            norm = _fold_ascii(span)
            if not norm or len(norm) < CARD_VARIANT_MIN_TOKEN:
                continue
            # Game keywords / terminology (deploy, boost, order, ...) and common
            # game verbs are NOT cards — never route them through card matching;
            # the keyword/terminology layer handles them. Fixes Deploy -> Decoy etc.
            if norm in self._game_terms or norm in AGGRESSIVE_SKIP_GAME_WORDS:
                continue
            # (a) accent-insensitive exact (Schirru -> Schirrú).
            if norm in norm_to_display:
                _emit(norm, span)
                continue
            # (b) reverse containment (Dagur -> Dagur Two Blades, Froth -> Golden
            #     Froth) — ONLY when unambiguous: the token must be a whole word
            #     of EXACTLY ONE longer canonical name, and not a faction or common
            #     word. Ambiguous fragments (Knight, Brokvar, Arachas) and factions
            #     (Skellige) are left to the strict extractor, which catches the
            #     full names (Redanian Knight, Brokvar Warrior ...) they belong to.
            sl = span.lower()
            if (sl not in self._factions
                    and norm not in lowercase_words
                    and norm not in CARD_VARIANT_COMMON_WORDS
                    and not is_likely_common_word(span)
                    and not is_likely_common_word(span.title())):
                longer = [c for c in word_to_norms.get(norm, ())
                          if len(c) > len(norm)]
                if len(longer) == 1:
                    _emit(longer[0], span)
                    continue
            # (c) edit distance for single words (Geraltt -> Geralt) — the risky
            #     step, so guard against common words (blacklist + comparative) and
            #     tighten the threshold for short tokens (<=6 chars use edit-dist 1
            #     so Deploy cannot reach Decoy at distance 2).
            if len(norm) >= CARD_FUZZY_MIN_TOKEN and _word_ok(norm, span):
                max_edit = (CARD_FUZZY_SHORT_MAX_EDIT
                            if len(norm) <= CARD_FUZZY_SHORT_MAXLEN
                            else CARD_FUZZY_MAX_EDIT)
                best = _best_fuzzy(norm, by_len, max_edit)
                if best:
                    _emit(best, span)

        # 2. Unresolved candidates (phrases) -> accent-exact or edit distance.
        for cand in unresolved or ():
            s = cand.strip()
            if not s:
                continue
            first = s.split()[0] if s.split() else s
            # Blacklist-only guard (NOT the comparative regex): the -er/-est rule
            # would wrongly drop real card names ending in -er (Yennefer), so
            # phrases rely on the curated SKIP_WORDS_FULL list to drop pure prose.
            if first in SKIP_WORDS_FULL or first.title() in SKIP_WORDS_FULL:
                continue
            norm = _fold_ascii(s)
            if len(norm) < CARD_FUZZY_MIN_TOKEN:
                continue
            if norm in norm_to_display:
                _emit(norm, s)
                continue
            best = _best_fuzzy(norm, by_len)
            if best:
                _emit(best, s)

        return results

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

        # Game terms (deploy / provision / order / Meta / deck names) usually appear
        # as single lowercase or capitalized words in prose and are missed by the
        # capitalized card-name extractors above. Scan them directly (word-boundary)
        # so the EN->CN lock covers them, matching the CN->EN dictionary lookup.
        for gt_lower, canonical_en in self._game_terms.items():
            if re.search(rf"\b{re.escape(gt_lower)}\b", text_lower):
                candidates.add(canonical_en)

        # Sort by length descending so full names are resolved before abbreviations.
        candidates = sorted(candidates, key=lambda x: (-len(x), x.lower()))

        results: list[dict] = []
        seen: set[tuple[str, str]] = set()
        unresolved: list[str] = []
        for cand in candidates:
            resolved = self.resolve(cand)
            if not resolved:
                unresolved.append(cand)
                continue
            seen_key = (resolved["canonical_en"].lower(), resolved["cn"])
            if seen_key in seen:
                continue
            seen.add(seen_key)
            results.append({"term": cand, **resolved})

        # Aggressive catch-all for VARIANTS the strict extractors/resolve missed
        # (reverse containment + edit distance, e.g. Double-Bladed Dagur,
        # Froth, Schirru, Geraltt of Rivia). Each hit resolves to the canonical
        # card and locks its official CN via the same mechanism above; the source
        # variant is recorded as the matched term.
        for canonical_en, variant in self._aggressive_card_matches(text, unresolved):
            resolved = self.resolve(canonical_en)
            if not resolved:
                continue
            seen_key = (resolved["canonical_en"].lower(), resolved["cn"])
            if seen_key in seen:
                continue
            seen.add(seen_key)
            results.append({"term": variant, **resolved})

        return results

    # --- CN->EN source extraction (dictionary lookup) -------------------------

    def _cn_to_ens_index(self) -> dict[str, list[dict]]:
        """Build the collision-aware CN -> [entry] map used by CN extraction.

        Joins self._cn_to_ens (CN -> [canonical_en]) to self._entries. Slang /
        community terms are deliberately NOT registered as hard terms, so their
        English is absent from _entries; a minimal synthetic record keeps them
        resolvable so they still surface from a Chinese source.
        """
        out: dict[str, list[dict]] = {}
        for cn, ens in self._cn_to_ens.items():
            entries: list[dict] = []
            for en in ens:
                e = self._entries.get(en.lower())
                if e:
                    entries.append(e)
                else:
                    entries.append({
                        "canonical_en": en, "cn": cn,
                        "source": "slang_map.md", "type": "slang",
                    })
            if entries:
                out[cn] = entries
        return out

    @staticmethod
    def _emit_cn_result(
        term: str,
        entries: list[dict],
        match_type: str,
        canonical_cn: str | None,
        results: list[dict],
        seen_terms: set[str],
    ) -> None:
        """Append one resolved CN->EN hit (single candidate or collision)."""
        if term in seen_terms:
            return
        cc = canonical_cn or entries[0].get("cn", term)
        seen_terms.add(term)
        ens = [e["canonical_en"] for e in entries]
        if len({e.lower() for e in ens}) <= 1:
            e0 = entries[0]
            results.append({
                "term": term,
                "canonical_en": e0["canonical_en"],
                "cn": cc,
                "source": e0.get("source", ""),
                "type": e0.get("type", ""),
                "match_type": match_type,
                "candidates": [{"en": e0["canonical_en"], "cn": cc}],
                "variants": [],
                "aliases": [],
                "abbrevs": [],
            })
        else:
            cands = [{"en": e["canonical_en"], "cn": e.get("cn", cc)}
                     for e in entries]
            results.append({
                "term": term,
                "canonical_en": "",
                "cn": cc,
                "source": entries[0].get("source", ""),
                "type": "ambiguous",
                "match_type": "cn_collision",
                "candidates": cands,
                "variants": cands,
                "aliases": [],
                "abbrevs": [],
            })

    def get_all_for_text_cn(self, text: str) -> list[dict]:
        """Extract known Chinese card/term names from a CN->EN source text.

        Mirror of get_all_for_text for the CN->EN direction. The existing
        extractors are English regexes and yield nothing on a Chinese source
        (empty lock -> silent-pass). This layer does dictionary lookup of every
        known Chinese name (4lang CN column + card_overrides + keywords /
        terminology / competitive / slang CN) found in the source, then:

          1. exact substring lookup (longest keys first),
          2. wrong->correct CN corrections (community / typo variants), and
          3. a bounded edit-distance fuzzy pass for single-char typos.

        Each hit resolves to its official English; a CN name shared by several
        cards (迪门家族水手 -> Dimun Pirate AND Dimun Corsair) is reported as a
        collision carrying every candidate.
        """
        if not text:
            return []

        cn_to_entries = self._cn_to_ens_index()
        results: list[dict] = []
        seen_terms: set[str] = set()
        matched: set[str] = set()

        # 1. Exact dictionary-substring lookup, longest CN keys first so a
        #    longer card name is matched before a shorter one it contains.
        #    Consume matched text spans so a short key that is a substring of an
        #    already-matched longer term (e.g. 松鼠 inside 松鼠党 -> Squirrel) is
        #    NOT separately matched to a different card.
        consumed: list[tuple[int, int]] = []
        for cn in sorted(cn_to_entries, key=len, reverse=True):
            if len(cn) < 2 or cn in matched:
                continue
            occ = next(
                (m for m in re.finditer(re.escape(cn), text)
                 if not any(not (m.end() <= s or m.start() >= e)
                            for s, e in consumed)),
                None,
            )
            if occ is None:
                continue
            consumed.append((occ.start(), occ.end()))
            matched.add(cn)
            self._emit_cn_result(cn, cn_to_entries[cn], "cn_exact",
                                 cn, results, seen_terms)

        # 2. wrong->correct CN corrections (card_overrides Renamed/Corrected,
        #    cn_fuzzy_fixes): a community/typo CN in the source resolves to the
        #    corrected CN's official English candidates.
        for wrong, correct in self._cn_corrections.items():
            if len(wrong) < 2 or wrong in matched or correct in matched:
                continue
            if wrong in text:
                entries = cn_to_entries.get(correct)
                if entries:
                    matched.add(wrong)
                    self._emit_cn_result(wrong, entries, "cn_correction",
                                         correct, results, seen_terms)

        # 3. Bounded fuzzy: overlapping all-hanzi windows of length 4..6 not
        #    matched exactly, within edit distance 1 of a known CN key of the
        #    same length. Restricted to PROPER-NOUN CARD names (>=4 chars): a
        #    3-char or terminology/slang key collides too often with ordinary
        #    prose (e.g. 测试句 ~ ptr/pts), and known typos are already covered
        #    by the correction layer above. Capped to bound cost/noise.
        by_len: dict[int, list[str]] = {}
        for cn, entries in cn_to_entries.items():
            if len(cn) >= 4 and all(e.get("type") == "card" for e in entries):
                by_len.setdefault(len(cn), []).append(cn)
        fuzzy_emitted = 0
        FUZZY_CAP = 25
        for L in range(4, 7):
            keys = by_len.get(L)
            if not keys:
                continue
            windows: set[str] = set()
            for m in re.finditer(rf"(?=([一-鿿]{{{L}}}))", text):
                windows.add(m.group(1))
            for w in windows:
                if w in matched or w in seen_terms:
                    continue
                hit = next((k for k in keys if _edit_distance(w, k) == 1), None)
                if hit:
                    self._emit_cn_result(w, cn_to_entries[hit], "cn_fuzzy",
                                         hit, results, seen_terms)
                    fuzzy_emitted += 1
                    if fuzzy_emitted >= FUZZY_CAP:
                        return results

        return results

    def get_slang_for_text(self, text: str) -> list[dict]:
        """Scan source text for community slang/jargon (lowercase-prose tolerant).

        Slang appears lowercase in prose (broken, on steroids) and is missed by
        the capitalized-phrase extractors. Mirrors the category lowercase scan in
        get_all_for_text but returns the slang record (intended CN + literal-forbidden)
        instead of a canonical term. Multi-word phrases (on steroids, sweet spot)
        match via re.escape on the whole phrase; trailing -s tolerated for plurals.
        """
        text_lower = text.lower()
        hits: list[dict] = []
        for key, rec in self._slang.items():
            if re.search(rf"\b{re.escape(key)}s?\b", text_lower):
                hits.append(rec)
        return hits

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


# --- Card-name indices for the residue scanners / card-reference extractors ---
#
# TermAuthority above is the resolution/locking layer. The terminology checker's
# residue scanner (check_english_residue / load_chinese_card_names), the pipeline's
# card-reference extractor (build_card_lookup_table), and learn.py each used to
# parse card_names.md directly. Those readers need a CARDS-ONLY map — not the mixed
# term+keyword+card _entries of TermAuthority, which would false-positive on common
# words like 'leader'/'mage'. These helpers build that cards-only map from the new
# 4lang table + card_overrides.md, keeping the scanners' behavior identical while
# switching the data source. Shared _parse_card_overrides keeps this and
# TermAuthority._load_card_overrides from drifting apart.

_card_data_cache: dict[str, dict] = {}


def _parse_card_overrides(path: "Path | str") -> dict:
    """Parse card_overrides.md into {overrides, aliases, renamed}.

    Section-aware (walks ## headers) so the three table schemas do not collide.
      overrides: list[(en, cn)]   direct EN->CN (force-win)
      aliases:   list[(alias, maps_to_en)]
      renamed:   dict[wrong_cn -> correct_cn]
    """
    overrides: list[tuple[str, str]] = []
    aliases: list[tuple[str, str]] = []
    renamed: dict[str, str] = {}

    path = Path(path)
    if not path.exists():
        return {"overrides": overrides, "aliases": aliases, "renamed": renamed}
    text = path.read_text(encoding="utf-8")

    section: str | None = None
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("## "):
            low = s.lower()
            # "Overrides" must not match "Leader Aliases" — guard the word.
            if low.startswith("## override"):
                section = "overrides"
            elif "leader alias" in low or low.startswith("## alias"):
                section = "aliases"
            elif "renamed" in low or "corrected" in low:
                section = "renamed"
            else:
                section = None
            continue
        if section is None or not s.startswith("|") or "---" in s:
            continue
        parts = [p.strip() for p in s.split("|")]
        if parts and not parts[0]:
            parts = parts[1:]
        if parts and not parts[-1]:
            parts = parts[:-1]
        if len(parts) < 2:
            continue
        a, b = parts[0], parts[1]
        if section == "overrides":
            if a and b and a.lower() != "english":
                overrides.append((a, b))
        elif section == "aliases":
            if a and b and a.lower() != "alias":
                aliases.append((a, b))
        elif section == "renamed":
            if a and b and a != "Skill原版" and a.lower() != "wrong":
                renamed[a] = b
    return {"overrides": overrides, "aliases": aliases, "renamed": renamed}


def _load_card_data(ref_dir: "Path | str") -> dict:
    """Build + cache the cards-only name indices for a references directory.

    Returns {en_index, cn_index, corrections}:
      en_index:    en_lower -> (en, cn)   (EN-residue + card-reference extract)
      cn_index:    cn -> en              (CN-residue scanning)
      corrections: wrong_cn -> correct_cn (Renamed/Corrected section)
    Cards come from card_names_4lang.json; manual overrides (leader aliases,
    direct EN->CN) are applied on top with override-wins priority.
    """
    ref_dir = Path(ref_dir)
    key = str(ref_dir)
    if key in _card_data_cache:
        return _card_data_cache[key]

    en_index: dict[str, tuple[str, str]] = {}
    cn_index: dict[str, str] = {}

    path = ref_dir / "card_names_4lang.json"
    if path.exists():
        import json
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data = {}
        for rec in data.values():
            en = (rec.get("en") or "").strip()
            cn = (rec.get("cn") or "").strip()
            if en and cn:
                en_index.setdefault(en.lower(), (en, cn))
                cn_index.setdefault(cn, en)

    parsed = _parse_card_overrides(ref_dir / "card_overrides.md")
    # Direct EN->CN overrides: force-win.
    for en, cn in parsed["overrides"]:
        en_index[en.lower()] = (en, cn)
        cn_index[cn] = en
    # Leader aliases: alias -> canonical's CN (canonical from the 4lang table).
    for alias, maps_to in parsed["aliases"]:
        canon = en_index.get(maps_to.lower())
        if canon:
            en_index[alias.lower()] = (alias, canon[1])
        else:
            en_index[alias.lower()] = (alias, maps_to)

    result = {
        "en_index": en_index,
        "cn_index": cn_index,
        "corrections": parsed["renamed"],
    }
    _card_data_cache[key] = result
    return result


def get_card_names_index(ref_dir: "Path | str | None" = None) -> dict[str, tuple[str, str]]:
    """Cards-only EN->CN index (en_lower -> (en, cn)) from card_names_4lang.json +
    card_overrides.md. Use for English-residue scanning and card-reference
    extraction. Contains ONLY card names (no terminology/keywords) so common
    words are not false-flagged as untranslated cards."""
    if ref_dir is None:
        ref_dir = Path(__file__).resolve().parent.parent / "references"
    return _load_card_data(ref_dir)["en_index"]


def get_card_names_cn_index(ref_dir: "Path | str | None" = None) -> dict[str, str]:
    """Cards-only CN->EN index (cn -> en): the mirror of get_card_names_index
    for scanning CN->EN translations for leftover Chinese card names."""
    if ref_dir is None:
        ref_dir = Path(__file__).resolve().parent.parent / "references"
    return _load_card_data(ref_dir)["cn_index"]


def get_card_name_corrections(ref_dir: "Path | str | None" = None) -> dict[str, str]:
    """CN wrong->correct corrections (wrong_cn -> correct_cn) from the
    Renamed/Corrected section of card_overrides.md."""
    if ref_dir is None:
        ref_dir = Path(__file__).resolve().parent.parent / "references"
    return _load_card_data(ref_dir)["corrections"]

