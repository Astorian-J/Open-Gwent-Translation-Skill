#!/usr/bin/env python3
"""
Gwent translation learning script.
Analyzes source + translated text to discover new terms not in references.
Outputs suggested additions to pending_terms.md for human review.

Usage:
    python learn.py <source_file> <translated_file> [--auto]

    source_file:      English source text
    translated_file:  Chinese translation
    --auto:           Write directly to pending_terms.md (default: preview only)
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter


def _get_ref_path(filename: str) -> Path:
    return Path(__file__).parent.parent / "references" / filename


def load_all_terms() -> dict[str, str]:
    """Load all known English terms and their Chinese translations.
    Returns: english_lower -> chinese mapping
    """
    terms = {}

    # From terminology_map.md — parse English/Chinese tables
    for fname in ["terminology_map.md"]:
        fpath = _get_ref_path(fname)
        if not fpath.exists():
            continue
        text = fpath.read_text(encoding="utf-8")
        in_table = False
        table_has_english = False
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("|") and "English" in line and "---" not in line:
                table_has_english = True
                in_table = False
                continue
            if line.startswith("|") and "---" in line and table_has_english:
                in_table = True
                continue
            if in_table and line.startswith("|") and "---" not in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4 and parts[1] and parts[2]:
                    en = parts[1]
                    cn = parts[2]
                    if any(ord(c) > 127 for c in en):
                        continue
                    if en not in ("English", "—", "") and cn not in ("Chinese", "—", ""):
                        for e in en.split("/"):
                            e = e.strip().lower()
                            if e:
                                terms[e] = cn
            if in_table and not line.startswith("|"):
                in_table = False
                table_has_english = False

    # From competitive_terms.md — parse English/Chinese/Abbreviations tables
    fpath = _get_ref_path("competitive_terms.md")
    if fpath.exists():
        text = fpath.read_text(encoding="utf-8")
        in_table = False
        table_has_english = False
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("|") and "English" in line and "---" not in line:
                table_has_english = True
                in_table = False
                continue
            if line.startswith("|") and "---" in line and table_has_english:
                in_table = True
                continue
            if in_table and line.startswith("|") and "---" not in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4 and parts[1] and parts[2]:
                    en = parts[1]
                    cn = parts[2]
                    if any(ord(c) > 127 for c in en):
                        continue
                    if en not in ("English", "—", "") and cn not in ("Chinese", "—", ""):
                        for e in en.split("/"):
                            e = e.strip().lower()
                            if e:
                                terms[e] = cn
                    # Parse abbreviations column (only for competitive_terms.md which has 4+ columns)
                    if len(parts) >= 5:
                        abbr = parts[3]
                        if abbr and abbr not in ("Abbreviations", "—", ""):
                            for a in abbr.split(";"):
                                a = a.strip().lower()
                                if a:
                                    terms[a] = cn
            if in_table and not line.startswith("|"):
                in_table = False
                table_has_english = False

    # From card_names.md — verified section
    card_file = _get_ref_path("card_names.md")
    if card_file.exists():
        text = card_file.read_text(encoding="utf-8")
        in_verified = False
        for line in text.split("\n"):
            line = line.strip()
            if "Verified" in line and "server" in line.lower():
                in_verified = True
                continue
            if in_verified and line.startswith("##") and "Renamed" in line:
                break
            if in_verified and line.startswith("|") and "---" not in line and "English" not in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4 and parts[1] and parts[1] != "English":
                    en = parts[1].lower()
                    cn = parts[2] if len(parts) > 2 else ""
                    if en and cn:
                        terms[en] = cn

    # From keywords_map.md
    kw_file = _get_ref_path("keywords_map.md")
    if kw_file.exists():
        text = kw_file.read_text(encoding="utf-8")
        in_table = False
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("|") and "---" in line and "English" in line:
                in_table = True
                continue
            if in_table and line.startswith("|") and "---" not in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4 and parts[1] and parts[1] != "English":
                    en = parts[1].lower()
                    cn = parts[2] if len(parts) > 2 else ""
                    if en and cn:
                        terms[en] = cn
            if in_table and not line.startswith("|"):
                in_table = False

    return terms


def load_pending_terms() -> list[dict]:
    """Load terms already in pending buffer."""
    pending = _get_ref_path("pending_terms.md")
    if not pending.exists():
        return []

    terms = []
    current = {}
    in_entry = False
    for line in pending.read_text(encoding="utf-8").split("\n"):
        if line.startswith("### "):
            if current:
                terms.append(current)
            current = {"source": line[4:].strip()}
            in_entry = True
        elif in_entry and line.startswith("- "):
            key, val = line[2:].split(":", 1)
            current[key.strip().lower()] = val.strip()
    if current:
        terms.append(current)

    return terms


def extract_candidate_terms(source_text: str) -> list[tuple[str, str]]:
    """Extract candidate terms from English source text.
    Returns: list of (term_type, term_text)
    """
    candidates = []

    # Pattern 1: Card names with colons (e.g., "Geralt: Igni", "Syanna: Duchess")
    # Limit word count to avoid matching full sentences
    for match in re.finditer(r'\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,2}:\s*(?:The\s+)?[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){0,2})\b', source_text):
        name = match.group(1).strip()
        # Sanity check: card names should be reasonably short
        if len(name) <= 40:
            candidates.append(("card", name))

    # Pattern 2: Multi-word capitalized phrases (potential card names)
    for match in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})\b', source_text):
        name = match.group(1).strip()
        # Filter out common words
        skip_words = {"The", "A", "An", "This", "That", "These", "Those", "It", "Its",
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
                      "Mostly", "Generally", "Typically", "Normally", "Commonly", "Usually",
                      "Frequently", "Regularly", "Consistently", "Constantly", "Continuously",
                      "Repeatedly", "Occasionally", "Rarely", "Seldom", "Hardly", "Barely",
                      "Scarcely", "Nearly", "Almost", "Approximately", "Roughly", "Around",
                      "About", "Over", "Under", "Above", "Below", "Between", "Among",
                      "Within", "Without", "Against", "Across", "Along", "Around", "Behind",
                      "Beyond", "Beside", "Besides", "Inside", "Outside", "Through",
                      "Throughout", "Toward", "Towards", "Upon", "Onto", "Into", "Off",
                      "Over", "Under", "Up", "Down", "In", "Out", "On", "At", "To", "For",
                      "Of", "With", "From", "By", "About", "Like", "As", "Into", "Through",
                      "During", "Before", "After", "Above", "Below", "Between", "Among",
                      "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
                      "Nine", "Ten", "First", "Second", "Third", "Last", "Next", "Previous",
                      "New", "Old", "Good", "Bad", "Big", "Small", "Long", "Short",
                      "High", "Low", "Great", "Little", "Large", "Tiny", "Huge", "Vast",
                      "Many", "Much", "More", "Most", "Some", "Any", "All", "None",
                      "Each", "Every", "Both", "Either", "Neither", "Other", "Another",
                      "Same", "Different", "Such", "Same", "Own", "Same", "Well", "Better",
                      "Best", "Bad", "Worse", "Worst", "Far", "Further", "Furthest",
                      "Near", "Nearer", "Nearest", "Early", "Earlier", "Earliest",
                      "Late", "Later", "Latest", "Soon", "Sooner", "Soonest", "Fast",
                      "Faster", "Fastest", "Slow", "Slower", "Slowest", "Hard", "Harder",
                      "Hardest", "Easy", "Easier", "Easiest", "Happy", "Happier",
                      "Happiest", "Sad", "Sadder", "Saddest", "Angry", "Angrier",
                      "Angriest", "Strong", "Stronger", "Strongest", "Weak", "Weaker",
                      "Weakest", "Rich", "Richer", "Richest", "Poor", "Poorer",
                      "Poorest", "Young", "Younger", "Youngest", "Old", "Older",
                      "Oldest", "Hot", "Hotter", "Hottest", "Cold", "Colder",
                      "Coldest", "Warm", "Warmer", "Warmest", "Cool", "Cooler",
                      "Coolest", "Dry", "Drier", "Driest", "Wet", "Wetter",
                      "Wettest", "Clean", "Cleaner", "Cleanest", "Dirty", "Dirtier",
                      "Dirtiest", "Deep", "Deeper", "Deepest", "Shallow", "Shallower",
                      "Shallowest", "Wide", "Wider", "Widest", "Narrow", "Narrower",
                      "Narrowest", "Thick", "Thicker", "Thickest", "Thin", "Thinner",
                      "Thinnest", "Heavy", "Heavier", "Heaviest", "Light", "Lighter",
                      "Lightest", "Bright", "Brighter", "Brightest", "Dark", "Darker",
                      "Darkest", "Loud", "Louder", "Loudest", "Quiet", "Quieter",
                      "Quietest", "Sharp", "Sharper", "Sharpest", "Dull", "Duller",
                      "Dullest", "Smooth", "Smoother", "Smoothest", "Rough", "Rougher",
                      "Roughest", "Soft", "Softer", "Softest", "Hard", "Harder",
                      "Hardest", "Tight", "Tighter", "Tightest", "Loose", "Looser",
                      "Loosest", "Safe", "Safer", "Safest", "Dangerous", "More",
                      "Most", "Careful", "More", "Most", "Brave", "Braver",
                      "Bravest", "Clever", "Cleverer", "Cleverest", "Stupid",
                      "Stupider", "Stupidest", "Friendly", "Friendlier",
                      "Friendliest", "Lovely", "Lovelier", "Loveliest", "Lively",
                      "Livelier", "Liveliest", "Lonely", "Lonelier", "Loneliest",
                      "Ugly", "Uglier", "Ugliest", "Pretty", "Prettier", "Prettiest",
                      "Healthy", "Healthier", "Healthiest", "Wealthy", "Wealthier",
                      "Wealthiest", "Hungry", "Hungrier", "Hungriest", "Thirsty",
                      "Thirstier", "Thirstiest", "Sleepy", "Sleepier", "Sleepiest",
                      "Funny", "Funnier", "Funniest", "Sunny", "Sunnier", "Sunniest",
                      "Windy", "Windier", "Windiest", "Rainy", "Rainier", "Rainiest",
                      "Snowy", "Snowier", "Snowiest", "Cloudy", "Cloudier",
                      "Cloudiest", "Foggy", "Foggier", "Fogiest", "Dusty", "Dustier",
                      "Dustiest", "Muddy", "Muddier", "Muddiest", "Bloody",
                      "Bloodier", "Bloodiest", "Merry", "Merrier", "Merriest",
                      "Gay", "Gayer", "Gayest", "Blue", "Bluer", "Bluest", "Red",
                      "Redder", "Reddest", "Green", "Greener", "Greenest",
                      "Yellow", "Yellower", "Yellowest", "White", "Whiter",
                      "Whitest", "Black", "Blacker", "Blackest", "Brown",
                      "Browner", "Brownest", "Gray", "Grayer", "Grayest",
                      "Purple", "Purpler", "Purplest", "Orange", "Oranger",
                      "Orangest", "Pink", "Pinker", "Pinkest", "Silver",
                      "Silverer", "Silverest", "Gold", "Golder", "Goldest",
                      "Bronze", "Bronzer", "Bronzest", "True", "Truer",
                      "Truest", "False", "Falser", "Falsest", "Right",
                      "Righter", "Rightest", "Wrong", "Wronger", "Wrongest",
                      "Correct", "More", "Most", "Exact", "Exacter",
                      "Exactest", "Perfect", "More", "Most", "Complete",
                      "More", "Most", "Whole", "Wholer", "Wholest", "Half",
                      "Half", "Halves", "Double", "Doubler", "Doublest",
                      "Triple", "Tripler", "Triplest", "Single", "Singler",
                      "Singlest", "Several", "Many", "Few", "Fewer",
                      "Fewest", "Numerous", "More", "Most", "Various",
                      "Diverse", "Different", "Similar", "Same", "Equal",
                      "Equivalent", "Alike", "Identical", "Distinct",
                      "Separate", "Individual", "Personal", "Private",
                      "Public", "Common", "Shared", "Joint", "Mutual",
                      "Reciprocal", "Collective", "Universal", "General",
                      "Specific", "Particular", "Special", "Unique",
                      "Rare", "Unusual", "Strange", "Weird", "Odd",
                      "Peculiar", "Curious", "Queer", "Funny", "Suspicious",
                      "Doubtful", "Uncertain", "Unsure", "Dubious",
                      "Questionable", "Debatable", "Disputable",
                      "Controversial", "Contentious", "Problematic",
                      "Troublesome", "Difficult", "Hard", "Tough",
                      "Rough", "Challenging", "Demanding", "Taxing",
                      "Arduous", "Strenuous", "Laborious", "Tedious",
                      "Tiresome", "Wearisome", "Boring", "Dull",
                      "Monotonous", "Repetitive", "Routine", "Habitual",
                      "Customary", "Traditional", "Conventional",
                      "Orthodox", "Standard", "Normal", "Regular",
                      "Ordinary", "Average", "Medium", "Moderate",
                      "Modest", "Reasonable", "Sensible", "Practical",
                      "Realistic", "Feasible", "Viable", "Possible",
                      "Achievable", "Attainable", "Accessible",
                      "Available", "Obtainable", "Reachable", "Within",
                      "Beyond", "Above", "Over", "Exceeding",
                      "Surpassing", "Transcending", "Transcendent",
                      "Superior", "Supreme", "Ultimate", "Final",
                      "Last", "Terminal", "Conclusive", "Definitive",
                      "Absolute", "Total", "Complete", "Full",
                      "Entire", "Whole", "Intact", "Undamaged",
                      "Unhurt", "Uninjured", "Safe", "Secure",
                      "Protected", "Guarded", "Defended", "Shielded",
                      "Sheltered", "Covered", "Hidden", "Concealed",
                      "Secret", "Private", "Confidential", "Classified",
                      "Restricted", "Limited", "Bound", "Tied",
                      "Connected", "Linked", "Related", "Associated",
                      "Connected", "Affiliated", "Allied", "United",
                      "Combined", "Joined", "Merged", "Fused",
                      "Blended", "Mixed", "Merged", "Integrated",
                      "Incorporated", "Included", "Contained",
                      "Enclosed", "Surrounded", "Encircled",
                      "Enclosed", "Wrapped", "Packaged", "Boxed",
                      "Crated", "Contained", "Held", "Kept",
                      "Stored", "Saved", "Preserved", "Maintained",
                      "Sustained", "Supported", "Upheld", "Backed",
                      "Endorsed", "Approved", "Accepted", "Recognized",
                      "Acknowledged", "Admitted", "Confessed",
                      "Declared", "Announced", "Proclaimed",
                      "Stated", "Said", "Told", "Spoken", "Expressed",
                      "Voiced", "Articulated", "Pronounced",
                      "Enunciated", "Uttered", "Murmured",
                      "Muttered", "Mumbled", "Whispered",
                      "Mouthed", "Lipped", "Signed", "Gestured",
                      "Indicated", "Pointed", "Shown", "Displayed",
                      "Exhibited", "Presented", "Demonstrated",
                      "Illustrated", "Exemplified", "Represented",
                      "Symbolized", "Signified", "Meant", "Implied",
                      "Suggested", "Hinted", "Intimated", "Insinuated",
                      "Inferred", "Deduced", "Concluded", "Reasoned",
                      "Thought", "Believed", "Considered", "Deemed",
                      "Regarded", "Viewed", "Seen", "Looked",
                      "Watched", "Observed", "Noticed", "Perceived",
                      "Sensed", "Felt", "Experienced", "Undergone",
                      "Endured", "Suffered", "Borne", "Withstood",
                      "Resisted", "Opposed", "Fought", "Battled",
                      "Struggled", "Strived", "Striven", "Worked",
                      "Labored", "Toiled", "Slogged", "Plugged",
                      "Persevered", "Persisted", "Continued",
                      "Proceeded", "Progressed", "Advanced",
                      "Moved", "Gone", "Travelled", "Journeyed",
                      "Voyaged", "Sailed", "Flown", "Ridden",
                      "Driven", "Walked", "Run", "Jumped",
                      "Leaped", "Hopped", "Skipped", "Danced",
                      "Swayed", "Swung", "Rocked", "Rolled",
                      "Turned", "Spun", "Whirled", "Twisted",
                      "Bent", "Curved", "Arched", "Bowed",
                      "Stooped", "Crouched", "Kneeled", "Knelt",
                      "Sat", "Lain", "Stood", "Risen", "Fallen",
                      "Dropped", "Descended", "Sunk", "Submerged",
                      "Dived", "Plunged", "Immersed", "Soaked",
                      "Drenched", "Saturated", "Filled", "Packed",
                      "Crammed", "Stuffed", "Crowded", "Congested",
                      "Overflowing", "Brimming", "Teeming",
                      "Abounding", "Thriving", "Flourishing",
                      "Prospering", "Booming", "Blossoming",
                      "Blooming", "Growing", "Developing",
                      "Evolving", "Expanding", "Extending",
                      "Stretching", "Spreading", "Scattering",
                      "Dispersing", "Distributing", "Sharing",
                      "Dividing", "Splitting", "Separating",
                      "Parting", "Breaking", "Cracking",
                      "Shattering", "Smashing", "Destroying",
                      "Ruining", "Wrecking", "Damaging",
                      "Harming", "Hurting", "Injuring",
                      "Wounding", "Cutting", "Slashing",
                      "Stabbing", "Piercing", "Penetrating",
                      "Puncturing", "Perforating", "Drilling",
                      "Boring", "Digging", "Excavating",
                      "Mining", "Quarrying", "Extracting",
                      "Removing", "Taking", "Getting",
                      "Obtaining", "Acquiring", "Gaining",
                      "Earning", "Winning", "Achieving",
                      "Accomplishing", "Fulfilling", "Completing",
                      "Finishing", "Ending", "Closing",
                      "Concluding", "Terminating", "Ceasing",
                      "Stopping", "Halting", "Pausing",
                      "Resting", "Relaxing", "Sleeping",
                      "Dreaming", "Imagining", "Fantasizing",
                      "Visualizing", "Envisioning", "Picturing",
                      "Conceiving", "Conceptualizing",
                      "Theorizing", "Hypothesizing",
                      "Speculating", "Guessing", "Estimating",
                      "Calculating", "Computing", "Figuring",
                      "Counting", "Measuring", "Weighing",
                      "Balancing", "Comparing", "Contrasting",
                      "Differentiating", "Distinguishing",
                      "Discriminating", "Separating",
                      "Categorizing", "Classifying",
                      "Organizing", "Arranging", "Ordering",
                      "Sorting", "Ranking", "Rating",
                      "Evaluating", "Assessing", "Appraising",
                      "Judging", "Critiquing", "Reviewing",
                      "Analyzing", "Examining", "Inspecting",
                      "Investigating", "Exploring", "Studying",
                      "Researching", "Searching", "Seeking",
                      "Looking", "Hunting", "Chasing",
                      "Pursuing", "Following", "Tracking",
                      "Tracing", "Finding", "Discovering",
                      "Detecting", "Locating", "Identifying",
                      "Recognizing", "Remembering", "Recalling",
                      "Recollecting", "Reminiscing", "Reflecting",
                      "Contemplating", "Meditating",
                      "Concentrating", "Focusing", "Attending",
                      "Listening", "Hearing", "Eavesdropping",
                      "Overhearing", "Sounding", "Ringing",
                      "Chiming", "Tolling", "Knocking",
                      "Tapping", "Rapping", "Patting",
                      "Touching", "Feeling", "Handling",
                      "Grasping", "Gripping", "Holding",
                      "Clutching", "Clinging", "Grabbing",
                      "Seizing", "Snatching", "Catching",
                      "Capturing", "Trapping", "Entangling",
                      "Ensnaring", "Entrapping", "Catching",
                      "Netting", "Bagging", "Landing",
                      "Securing", "Obtaining", "Procuring",
                      "Fetching", "Retrieving", "Recovering",
                      "Reclaiming", "Regaining", "Restoring",
                      "Returning", "Bringing", "Carrying",
                      "Bearing", "Transporting", "Conveying",
                      "Transmitting", "Sending", "Dispatching",
                      "Shipping", "Mailing", "Posting",
                      "Delivering", "Handing", "Passing",
                      "Transferring", "Moving", "Shifting",
                      "Sliding", "Gliding", "Slipping",
                      "Creeping", "Crawling", "Climbing",
                      "Scaling", "Ascending", "Clambering",
                      "Scrambling", "Struggling", "Striving",
                      "Trying", "Attempting", "Endeavoring",
                      "Undertaking", "Venturing", "Daring",
                      "Risking", "Gambling", "Betting",
                      "Wagering", "Staking", "Pledging",
                      "Promising", "Vowing", "Swearing",
                      "Oathing", "Pledging", "Committing",
                      "Dedicating", "Devoting", "Consecrating",
                      "Sacrificing", "Offering", "Giving",
                      "Donating", "Contributing", "Providing",
                      "Supplying", "Furnishing", "Equipping",
                      "Arming", "Preparing", "Readying",
                      "Setting", "Fixing", "Establishing",
                      "Founding", "Creating", "Making",
                      "Building", "Constructing", "Erecting",
                      "Raising", "Lifting", "Hoisting",
                      "Elevating", "Uplifting", "Boosting",
                      "Increasing", "Raising", "Growing",
                      "Expanding", "Enlarging", "Magnifying",
                      "Amplifying", "Intensifying", "Strengthening",
                      "Reinforcing", "Fortifying", "Consolidating",
                      "Solidifying", "Hardening", "Toughening",
                      "Tempering", "Annealing", "Forging",
                      "Casting", "Molding", "Shaping",
                      "Forming", "Fashioning", "Crafting",
                      "Designing", "Planning", "Scheming",
                      "Plotting", "Conspiring", "Colluding",
                      "Cooperating", "Collaborating",
                      "Coordinating", "Synchronizing",
                      "Harmonizing", "Aligning", "Matching",
                      "Pairing", "Coupling", "Linking",
                      "Connecting", "Joining", "Uniting",
                      "Combining", "Integrating", "Fusing",
                      "Merging", "Blending", "Mixing",
                      "Stirring", "Shaking", "Agitating",
                      "Disturbing", "Perturbing", "Disrupting",
                      "Interrupting", "Disturbing", "Bothering",
                      "Annoying", "Irritating", "Aggravating",
                      "Exasperating", "Infuriating",
                      "Enraging", "Angering", "Provoking",
                      "Inciting", "Instigating", "Fomenting",
                      "Stirring", "Rousing", "Awakening",
                      "Waking", "Arising", "Emerging",
                      "Appearing", "Materializing",
                      "Manifesting", "Showing", "Displaying",
                      "Exhibiting", "Revealing", "Disclosing",
                      "Exposing", "Uncovering", "Unveiling",
                      "Unmasking", "Unearthing", "Digging",
                      "Excavating", "Mining", "Extracting",
                      "Deriving", "Obtaining", "Getting",
                      "Acquiring", "Gaining", "Winning",
                      "Earning", "Deserving", "Meriting",
                      "Warranting", "Justifying", "Validating",
                      "Confirming", "Verifying", "Authenticating",
                      "Certifying", "Attesting", "Testifying",
                      "Witnessing", "Seeing", "Observing",
                      "Noticing", "Perceiving", "Sensing",
                      "Feeling", "Experiencing", "Undergoing",
                      "Suffering", "Enduring", "Tolerating",
                      "Enduring", "Bearing", "Withstanding",
                      "Resisting", "Opposing", "Defying",
                      "Challenging", "Confronting", "Facing",
                      "Meeting", "Encountering", "Experiencing",
                      "Undergoing", "Suffering", "Enduring"}
        first_word = name.split()[0]
        if first_word in skip_words or len(name) < 4:
            continue
        candidates.append(("phrase", name))

    # Pattern 3: All-caps abbreviations (2-5 chars)
    for match in re.finditer(r'\b([A-Z]{2,5})\b', source_text):
        abbrev = match.group(1)
        # Skip common non-Gwent abbreviations
        skip_abbrevs = {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU",
                        "ALL", "ANY", "CAN", "HAD", "HER", "WAS", "ONE",
                        "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS",
                        "HOW", "ITS", "MAY", "NEW", "NOW", "OLD", "SEE",
                        "TWO", "WAY", "WHO", "BOY", "DID", "EYE", "MAN",
                        "MEN", "MRS", "MRS", "MRS", "MRS", "MRS"}
        if abbrev in skip_abbrevs:
            continue
        candidates.append(("abbrev", abbrev))

    # Pattern 4: Words with special Gwent notation
    for match in re.finditer(r'\b([A-Z][a-z]+)\s+(?:for)\s+(\d+)\b', source_text):
        candidates.append(("phrase", match.group(0)))

    return candidates


def find_unknown_terms(source_text: str, translated_text: str) -> list[dict]:
    """Find terms in source that are not in our reference database."""
    known = load_all_terms()
    candidates = extract_candidate_terms(source_text)

    unknown = []
    seen = set()

    for term_type, term_text in candidates:
        key = term_text.lower()
        if key in seen:
            continue
        seen.add(key)

        # Check if known (fuzzy match)
        if key in known:
            continue

        # Check if any known term contains this
        found_parent = False
        for known_en in known:
            if key in known_en or known_en in key:
                found_parent = True
                break
        if found_parent:
            continue

        # Check if already in pending
        pending = load_pending_terms()
        in_pending = any(p.get("source", "").lower() == key for p in pending)
        if in_pending:
            continue

        # Try to find Chinese translation in the translated text
        # Simple heuristic: look for Chinese text near where this term might be
        cn_translation = ""

        unknown.append({
            "type": term_type,
            "source": term_text,
            "translation": cn_translation,
            "confidence": "low"  # Requires human verification
        })

    # Sort by type priority: card > abbrev > phrase
    type_order = {"card": 0, "abbrev": 1, "phrase": 2}
    unknown.sort(key=lambda x: type_order.get(x["type"], 3))

    return unknown


def format_pending_entry(term: dict) -> str:
    """Format a single term as markdown entry."""
    lines = [
        f"### {term['source']}",
        f"- Type: {term['type']}",
        f"- Suggested: {term['translation'] or '(translate and verify)'}",
        f"- Confidence: {term['confidence']}",
        f"- Discovered: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}",
        "- Status: pending review",
        ""
    ]
    return "\n".join(lines)


def preview_new_terms(source_text: str, translated_text: str) -> list[dict]:
    """Preview new terms without writing to file."""
    unknown = find_unknown_terms(source_text, translated_text)

    if not unknown:
        print("No new terms discovered.")
        return []

    print(f"Discovered {len(unknown)} potential new term(s):\n")

    for term in unknown:
        print(f"  [{term['type']}] {term['source']}")
        if term['translation']:
            print(f"           → {term['translation']}")
        print()

    return unknown


def add_to_pending(terms: list[dict]) -> int:
    """Add terms to pending_terms.md. Returns count added."""
    pending_path = _get_ref_path("pending_terms.md")

    # Create file with header if not exists
    if not pending_path.exists():
        pending_path.write_text(
            "# Pending Terms (待审核术语)\n\n"
            "Terms discovered during translation that need human review.\n"
            "After verification, move confirmed entries to the appropriate reference file.\n\n"
            "---\n\n",
            encoding="utf-8"
        )

    content = pending_path.read_text(encoding="utf-8")

    # Check for duplicates
    existing_sources = set()
    for line in content.split("\n"):
        if line.startswith("### "):
            existing_sources.add(line[4:].strip().lower())

    added = 0
    with open(pending_path, "a", encoding="utf-8") as f:
        for term in terms:
            if term["source"].lower() in existing_sources:
                continue
            f.write(format_pending_entry(term))
            added += 1

    return added


def main():
    if len(sys.argv) < 3:
        print("Usage: python learn.py <source_file> <translated_file> [--auto]")
        print("  --auto: Write directly to pending_terms.md")
        sys.exit(1)

    source_file = sys.argv[1]
    translated_file = sys.argv[2]
    auto_write = "--auto" in sys.argv

    source_text = Path(source_file).read_text(encoding="utf-8")
    translated_text = Path(translated_file).read_text(encoding="utf-8")

    unknown = preview_new_terms(source_text, translated_text)

    if not unknown:
        sys.exit(0)

    if auto_write:
        added = add_to_pending(unknown)
        print(f"Added {added} term(s) to pending_terms.md")
    else:
        print("Preview mode. Run with --auto to write to pending_terms.md")
        print("Or manually add confirmed terms to the appropriate reference file.")


if __name__ == "__main__":
    main()
