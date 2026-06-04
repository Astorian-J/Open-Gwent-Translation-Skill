#!/usr/bin/env python3
"""Shared utilities for gwent-translation-style scripts.

Extracted to eliminate duplication of proper-noun extraction logic
across learn.py, context_lock.py, and diff_review.py.
"""

import re
from collections.abc import Iterator

# --- Regex patterns ---

CARD_NAME_PATTERN = re.compile(
    r'\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,2}:\s*(?:The\s+)?'
    r'[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,2})\b'
)

ABBREVIATION_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')

# --- Skip sets ---

# Minimal skip words used by context_lock.py and diff_review.py.
SKIP_WORDS_MINIMAL: frozenset[str] = frozenset({
    "The", "This", "That", "These", "Those", "They", "There", "Then",
    "When", "What", "Where", "Which", "While", "Although", "However",
})

# Full skip words used by learn.py for aggressive false-positive filtering.
SKIP_WORDS_FULL: frozenset[str] = frozenset({
    "The", "A", "An", "This", "That", "These", "Those", "It", "Its",
    "He", "She", "They", "We", "You", "I", "Me", "My", "His", "Her",
    "Their", "Our", "Your", "And", "Or", "But", "If", "Then", "Than",
    "When", "Where", "Why", "How", "What", "Who", "Which", "While",
    "Because", "Since", "Until", "Although", "However", "Therefore",
    "Moreover", "Furthermore", "Nevertheless", "Otherwise", "Instead",
    "Meanwhile", "Afterwards", "Previously", "Eventually", "Finally",
    "Currently", "Recently", "Usually", "Often", "Sometimes", "Always",
    "Never", "Already", "Still", "Yet", "Even", "Just", "Only", "Also",
    "Too", "Very", "Quite", "Rather", "Pretty", "Really", "Actually",
    "Probably", "Possibly", "Perhaps", "Maybe", "Certainly", "Definitely",
    "Absolutely", "Completely", "Totally", "Entirely", "Fully", "Highly",
    "Extremely", "Incredibly", "Amazingly", "Surprisingly", "Interestingly",
    "Fortunately", "Unfortunately", "Luckily", "Hopefully", "Ideally",
    "Basically", "Essentially", "Fundamentally", "Primarily", "Mainly",
    "Mostly", "Generally", "Typically", "Normally", "Commonly",
    "Frequently", "Regularly", "Consistently", "Constantly", "Continuously",
    "Repeatedly", "Occasionally", "Rarely", "Seldom", "Hardly", "Barely",
    "Scarcely", "Nearly", "Almost", "Approximately", "Roughly", "Around",
    "About", "Over", "Under", "Above", "Below", "Between", "Among",
    "Within", "Without", "Against", "Across", "Along", "Behind",
    "Beyond", "Beside", "Besides", "Inside", "Outside", "Through",
    "Throughout", "Toward", "Towards", "Upon", "Onto", "Into", "Off",
    "Up", "Down", "In", "Out", "On", "At", "To", "For",
    "Of", "With", "From", "By", "About", "Like", "As", "During",
    "Before", "After", "One", "Two", "Three", "Four", "Five", "Six",
    "Seven", "Eight", "Nine", "Ten", "First", "Second", "Third",
    "Last", "Next", "Previous", "New", "Old", "Good", "Bad", "Big",
    "Small", "Long", "Short", "High", "Low", "Great", "Little",
    "Large", "Tiny", "Huge", "Vast", "Many", "Much", "More", "Most",
    "Some", "Any", "All", "None", "Each", "Every", "Both", "Either",
    "Neither", "Other", "Another", "Same", "Different", "Such", "Own",
    "Well", "Better", "Best", "Worse", "Worst", "Far", "Further",
    "Furthest", "Near", "Nearer", "Nearest", "Early", "Earlier",
    "Earliest", "Late", "Later", "Latest", "Soon", "Sooner", "Soonest",
    "Fast", "Faster", "Fastest", "Slow", "Slower", "Slowest", "Hard",
    "Harder", "Hardest", "Easy", "Easier", "Easiest", "Happy",
    "Happier", "Happiest", "Sad", "Sadder", "Saddest", "Angry",
    "Angrier", "Angriest", "Strong", "Stronger", "Strongest", "Weak",
    "Weaker", "Weakest", "Rich", "Richer", "Richest", "Poor", "Poorer",
    "Poorest", "Young", "Younger", "Youngest", "Old", "Older", "Oldest",
    "Hot", "Hotter", "Hottest", "Cold", "Colder", "Coldest", "Warm",
    "Warmer", "Warmest", "Cool", "Cooler", "Coolest", "Dry", "Drier",
    "Driest", "Wet", "Wetter", "Wettest", "Clean", "Cleaner",
    "Cleanest", "Dirty", "Dirtier", "Dirtiest", "Deep", "Deeper",
    "Deepest", "Shallow", "Shallower", "Shallowest", "Wide", "Wider",
    "Widest", "Narrow", "Narrower", "Narrowest", "Thick", "Thicker",
    "Thickest", "Thin", "Thinner", "Thinnest", "Heavy", "Heavier",
    "Heaviest", "Light", "Lighter", "Lightest", "Bright", "Brighter",
    "Brightest", "Dark", "Darker", "Darkest", "Loud", "Louder",
    "Loudest", "Quiet", "Quieter", "Quietest", "Sharp", "Sharper",
    "Sharpest", "Dull", "Duller", "Dullest", "Smooth", "Smoother",
    "Smoothest", "Rough", "Rougher", "Roughest", "Soft", "Softer",
    "Softest", "Tight", "Tighter", "Tightest", "Loose", "Looser",
    "Loosest", "Safe", "Safer", "Safest", "Dangerous", "Careful",
    "Brave", "Braver", "Bravest", "Clever", "Cleverer", "Cleverest",
    "Stupid", "Stupider", "Stupidest", "Friendly", "Friendlier",
    "Friendliest", "Lovely", "Lovelier", "Loveliest", "Lively",
    "Livelier", "Liveliest", "Lonely", "Lonelier", "Loneliest",
    "Ugly", "Uglier", "Ugliest", "Pretty", "Prettier", "Prettiest",
    "Healthy", "Healthier", "Healthiest", "Wealthy", "Wealthier",
    "Wealthiest", "Hungry", "Hungrier", "Hungriest", "Thirsty",
    "Thirstier", "Thirstiest", "Sleepy", "Sleepier", "Sleepiest",
    "Funny", "Funnier", "Funniest", "Sunny", "Sunnier", "Sunniest",
    "Windy", "Windier", "Windiest", "Rainy", "Rainier", "Rainiest",
    "Snowy", "Snowier", "Snowiest", "Cloudy", "Cloudier", "Cloudiest",
    "Foggy", "Foggier", "Fogiest", "Dusty", "Dustier", "Dustiest",
    "Muddy", "Muddier", "Muddiest", "Bloody", "Bloodier", "Bloodiest",
    "Merry", "Merrier", "Merriest", "Gay", "Gayer", "Gayest", "Blue",
    "Bluer", "Bluest", "Red", "Redder", "Reddest", "Green", "Greener",
    "Greenest", "Yellow", "Yellower", "Yellowest", "White", "Whiter",
    "Whitest", "Black", "Blacker", "Blackest", "Brown", "Browner",
    "Brownest", "Gray", "Grayer", "Grayest", "Purple", "Purpler",
    "Purplest", "Orange", "Oranger", "Orangest", "Pink", "Pinker",
    "Pinkest", "Silver", "Silverer", "Silverest", "Gold", "Golder",
    "Goldest", "Bronze", "Bronzer", "Bronzest", "True", "Truer",
    "Truest", "False", "Falser", "Falsest", "Right", "Righter",
    "Rightest", "Wrong", "Wronger", "Wrongest", "Correct", "Exact",
    "Exacter", "Exactest", "Perfect", "Complete", "Whole", "Wholer",
    "Wholest", "Half", "Double", "Doubler", "Doublest", "Triple",
    "Tripler", "Triplest", "Single", "Singler", "Singlest", "Several",
    "Many", "Few", "Fewer", "Fewest", "Numerous", "Various", "Diverse",
    "Similar", "Equal", "Equivalent", "Alike", "Identical", "Distinct",
    "Separate", "Individual", "Personal", "Private", "Public", "Common",
    "Shared", "Joint", "Mutual", "Reciprocal", "Collective", "Universal",
    "General", "Specific", "Particular", "Special", "Unique", "Rare",
    "Unusual", "Strange", "Weird", "Odd", "Peculiar", "Curious", "Queer",
    "Suspicious", "Doubtful", "Uncertain", "Unsure", "Dubious",
    "Questionable", "Debatable", "Disputable", "Controversial",
    "Contentious", "Problematic", "Troublesome", "Difficult", "Tough",
    "Rough", "Challenging", "Demanding", "Taxing", "Arduous",
    "Strenuous", "Laborious", "Tedious", "Tiresome", "Wearisome",
    "Boring", "Monotonous", "Repetitive", "Routine", "Habitual",
    "Customary", "Traditional", "Conventional", "Orthodox", "Standard",
    "Normal", "Regular", "Ordinary", "Average", "Medium", "Moderate",
    "Modest", "Reasonable", "Sensible", "Practical", "Realistic",
    "Feasible", "Viable", "Possible", "Achievable", "Attainable",
    "Accessible", "Available", "Obtainable", "Reachable", "Within",
    "Beyond", "Exceeding", "Surpassing", "Transcending", "Transcendent",
    "Superior", "Supreme", "Ultimate", "Final", "Terminal", "Conclusive",
    "Definitive", "Absolute", "Total", "Full", "Entire", "Intact",
    "Undamaged", "Unhurt", "Uninjured", "Secure", "Protected", "Guarded",
    "Defended", "Shielded", "Sheltered", "Covered", "Hidden", "Concealed",
    "Secret", "Confidential", "Classified", "Restricted", "Limited",
    "Bound", "Tied", "Connected", "Linked", "Related", "Associated",
    "Affiliated", "Allied", "United", "Combined", "Joined", "Merged",
    "Fused", "Blended", "Mixed", "Integrated", "Incorporated",
    "Included", "Contained", "Enclosed", "Surrounded", "Encircled",
    "Wrapped", "Packaged", "Boxed", "Crated", "Held", "Kept", "Stored",
    "Saved", "Preserved", "Maintained", "Sustained", "Supported",
    "Upheld", "Backed", "Endorsed", "Approved", "Accepted", "Recognized",
    "Acknowledged", "Admitted", "Confessed", "Declared", "Announced",
    "Proclaimed", "Stated", "Said", "Told", "Spoken", "Expressed",
    "Voiced", "Articulated", "Pronounced", "Enunciated", "Uttered",
    "Murmured", "Muttered", "Mumbled", "Whispered", "Mouthed", "Lipped",
    "Signed", "Gestured", "Indicated", "Pointed", "Shown", "Displayed",
    "Exhibited", "Presented", "Demonstrated", "Illustrated",
    "Exemplified", "Represented", "Symbolized", "Signified", "Meant",
    "Implied", "Suggested", "Hinted", "Intimated", "Insinuated",
    "Inferred", "Deduced", "Concluded", "Reasoned", "Thought",
    "Believed", "Considered", "Deemed", "Regarded", "Viewed", "Seen",
    "Looked", "Watched", "Observed", "Noticed", "Perceived", "Sensed",
    "Felt", "Experienced", "Undergone", "Endured", "Suffered", "Borne",
    "Withstood", "Resisted", "Opposed", "Defied", "Challenged",
    "Confronted", "Facing", "Meeting", "Encountered", "Trying",
    "Attempting", "Endeavoring", "Undertaking", "Venturing", "Daring",
    "Risking", "Gambling", "Betting", "Wagering", "Staking", "Pledging",
    "Promising", "Vowing", "Swearing", "Oathing", "Committing",
    "Dedicating", "Devoting", "Consecrating", "Sacrificing", "Offering",
    "Giving", "Donating", "Contributing", "Providing", "Supplying",
    "Furnishing", "Equipping", "Arming", "Preparing", "Readying",
    "Setting", "Fixing", "Establishing", "Founding", "Creating",
    "Making", "Building", "Constructing", "Erecting", "Raising",
    "Lifting", "Hoisting", "Elevating", "Uplifting", "Boosting",
    "Increasing", "Growing", "Expanding", "Enlarging", "Magnifying",
    "Amplifying", "Intensifying", "Strengthening", "Reinforcing",
    "Fortifying", "Consolidating", "Solidifying", "Hardening",
    "Toughening", "Tempering", "Annealing", "Forging", "Casting",
    "Molding", "Shaping", "Forming", "Fashioning", "Crafting",
    "Designing", "Planning", "Scheming", "Plotting", "Conspiring",
    "Colluding", "Cooperating", "Collaborating", "Coordinating",
    "Synchronizing", "Harmonizing", "Aligning", "Matching", "Pairing",
    "Coupling", "Linking", "Connecting", "Joining", "Uniting",
    "Combining", "Integrating", "Fusing", "Merging", "Blending",
    "Mixing", "Stirring", "Shaking", "Agitating", "Disturbing",
    "Perturbing", "Disrupting", "Interrupting", "Bothering",
    "Annoying", "Irritating", "Aggravating", "Exasperating",
    "Infuriating", "Enraging", "Angering", "Provoking", "Inciting",
    "Instigating", "Fomenting", "Stirring", "Rousing", "Awakening",
    "Waking", "Arising", "Emerging", "Appearing", "Materializing",
    "Manifesting", "Showing", "Revealing", "Disclosing", "Exposing",
    "Uncovering", "Unveiling", "Unmasking", "Unearthing", "Digging",
    "Excavating", "Mining", "Extracting", "Deriving", "Obtaining",
    "Getting", "Acquiring", "Gaining", "Winning", "Earning",
    "Deserving", "Meriting", "Warranting", "Justifying", "Validating",
    "Confirming", "Verifying", "Authenticating", "Certifying",
    "Attesting", "Testifying", "Witnessing", "Seeing", "Observing",
    "Noticing", "Perceiving", "Sensing", "Feeling", "Experiencing",
    "Undergoing", "Suffering", "Enduring", "Tolerating", "Bearing",
    "Resisting", "Opposing", "Defying", "Challenging", "Confronting",
    "Facing", "Meeting", "Encountered", "Experienced", "Undergone",
})

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
