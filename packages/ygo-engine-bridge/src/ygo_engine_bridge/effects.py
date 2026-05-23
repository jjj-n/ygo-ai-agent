"""Card effect text analysis utilities for AI decision-making.

Provides keyword-based effect classification and value estimation
without requiring full NLP — uses pattern matching on common
Yu-Gi-Oh! effect text conventions (Chinese and English).
"""

from __future__ import annotations
import re


# Card type constants
TYPE_MONSTER = 0x1
TYPE_SPELL = 0x2
TYPE_TRAP = 0x4
TYPE_FUSION = 0x40
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_LINK = 0x4000000
TYPE_PENDULUM = 0x1000000


# Keyword patterns for effect classification
# Each pattern has (compiled_regex, category, value_weight)
_KEYWORD_PATTERNS = [
    # Board wipes - highest value
    (re.compile(r'(destroy\s+all|destroy\s+every|destroy\s+each|破坏.*全部|破坏.*所有|全部.*破坏)', re.I),
     "board_wipe", 9.0),
    (re.compile(r'(destroy\s+all\s+monster|destroy\s+all\s+Spell|destroy\s+all\s+Trap|怪兽.*全部.*破坏|魔法.*全部.*破坏|陷阱.*全部.*破坏)', re.I),
     "board_wipe", 9.5),

    # Single destruction
    (re.compile(r'(destroy\s+1|destroy\s+that|destroy\s+the\s+target|破坏.*1张|破坏.*那|破坏.*对象)', re.I),
     "destroy", 6.0),

    # Card draw
    (re.compile(r'(draw\s+(\d+)\s+card|抽.*(\d+).*卡|从卡组抽卡)', re.I),
     "draw", 7.0),

    # Search / add from deck
    (re.compile(r'(add\s+\d+.*from.*[Dd]eck.*hand|search.*from.*deck|从卡组.*加入手牌|卡组.*加入手牌|卡组.*检索)', re.I),
     "search", 8.0),

    # Negation
    (re.compile(r'(negate\s+the\s+activation|negate\s+the\s+effect|无效.*发动|无效.*效果|使.*无效)', re.I),
     "negate", 8.5),

    # Special summon from deck
    (re.compile(r'(special\s+summon.*from.*[Dd]eck|从卡组.*特殊召唤|卡组.*特殊召唤)', re.I),
     "summon_from_deck", 8.0),

    # Special summon from GY
    (re.compile(r'(special\s+summon.*from.*[Gg]raveyard|从墓地.*特殊召唤|墓地.*特殊召唤)', re.I),
     "summon_from_gy", 6.5),

    # Generic special summon
    (re.compile(r'(special\s+summon|特殊召唤)', re.I),
     "special_summon", 5.0),

    # Banish / remove
    (re.compile(r'(banish|remove\s+from\s+play|除外)', re.I),
     "banish", 6.0),

    # LP recovery
    (re.compile(r'(gain\s+\d+.*LP|recover\s+\d+.*LP|恢复.*生命值|回复.*LP)', re.I),
     "lp_recover", 4.0),

    # LP damage (burn)
    (re.compile(r'(take\s+\d+.*damage|inflict\s+\d+.*damage|受到.*伤害|给予.*伤害)', re.I),
     "burn", 5.5),

    # Protection
    (re.compile(r'(cannot\s+be\s+destroyed|unaffected\s+by|不会被破坏|不受.*影响)', re.I),
     "protection", 7.0),

    # Return to hand
    (re.compile(r'(return.*hand|回到.*手牌|返回.*手牌)', re.I),
     "bounce", 5.0),

    # Send to GY
    (re.compile(r'(send.*to.*[Gg]raveyard|送去墓地|送入墓地)', re.I),
     "send_to_gy", 5.5),

    # Equip
    (re.compile(r'(equip|equip\s+card|装备)', re.I),
     "equip", 3.0),

    # Counter trap
    (re.compile(r'(counter\s+trap|反击陷阱)', re.I),
     "counter_trap", 7.5),
]


def classify_effect(effect_text: str) -> dict:
    """Classify a card effect text into categories.

    Returns dict with:
    - keywords: list of detected keyword categories
    - value_score: float 0-10 indicating estimated card value
    - summary: one-line human-readable summary
    """
    if not effect_text:
        return {"keywords": [], "value_score": 0.0, "summary": "No effect"}

    keywords = []
    max_value = 0.0

    for pattern, category, weight in _KEYWORD_PATTERNS:
        if pattern.search(effect_text):
            if category not in keywords:
                keywords.append(category)
            max_value = max(max_value, weight)

    # Generate summary
    summary = _generate_summary(effect_text, keywords)

    return {
        "keywords": keywords,
        "value_score": max_value,
        "summary": summary,
    }


def summarize_effect(effect_text: str) -> str:
    """Create a short (one-line) summary of the card effect for LLM context."""
    if not effect_text:
        return "No effect"

    classification = classify_effect(effect_text)
    return classification["summary"]


def estimate_card_value(effect_text: str, card_type: int = 0) -> float:
    """Estimate the strategic value of a card based on its effect text.

    Returns a score from 0-10 where higher is more valuable.

    Considers:
    - Effect keywords and their strategic importance
    - Card type bonuses (counter traps, quick effects)
    """
    if not effect_text:
        return 0.0

    classification = classify_effect(effect_text)
    base_value = classification["value_score"]

    # Bonus for counter traps
    if card_type & TYPE_TRAP and "counter_trap" in classification["keywords"]:
        base_value = max(base_value, 7.5)

    # Bonus for quick-play spells (often more flexible)
    if card_type & 0x10000:  # TYPE_QUICKPLAY
        base_value = min(10.0, base_value + 1.0)

    return min(10.0, base_value)


def _generate_summary(effect_text: str, keywords: list[str]) -> str:
    """Generate a one-line summary from keywords."""
    if not keywords:
        return "Vanilla / Continuous effect"

    summary_parts = []
    keyword_descriptions = {
        "board_wipe": "Board wipe",
        "destroy": "Destroys cards",
        "draw": "Draws cards",
        "search": "Searches from deck",
        "negate": "Negates effects",
        "summon_from_deck": "Summons from deck",
        "summon_from_gy": "Summons from GY",
        "special_summon": "Special summons",
        "banish": "Banishes cards",
        "lp_recover": "Recovers LP",
        "burn": "Burns LP",
        "protection": "Protection",
        "bounce": "Returns to hand",
        "send_to_gy": "Sends to GY",
        "equip": "Equip effect",
        "counter_trap": "Counter trap",
    }

    for kw in keywords[:3]:  # Top 3 keywords
        if kw in keyword_descriptions:
            summary_parts.append(keyword_descriptions[kw])

    return " / ".join(summary_parts) if summary_parts else "Effect monster"


def get_effect_priority(effect_text: str) -> int:
    """Get a priority score for activation order (higher = activate first).

    Used for deciding which card to activate when multiple are available.
    """
    if not effect_text:
        return 0

    classification = classify_effect(effect_text)

    # Priority ordering for activation
    priority_map = {
        "negate": 100,
        "board_wipe": 90,
        "search": 80,
        "draw": 75,
        "summon_from_deck": 70,
        "destroy": 60,
        "banish": 55,
        "summon_from_gy": 50,
        "burn": 45,
        "special_summon": 40,
        "protection": 35,
        "bounce": 30,
        "send_to_gy": 25,
        "lp_recover": 20,
        "equip": 10,
        "counter_trap": 85,
    }

    max_priority = 0
    for kw in classification["keywords"]:
        max_priority = max(max_priority, priority_map.get(kw, 0))

    return max_priority


def is_extra_deck_type(card_type: int) -> bool:
    """Check if a card type is an extra deck monster type."""
    return bool(card_type & (TYPE_FUSION | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK))


def get_extra_deck_type_name(card_type: int) -> str:
    """Get the extra deck type name for display."""
    types = []
    if card_type & TYPE_FUSION:
        types.append("Fusion")
    if card_type & TYPE_SYNCHRO:
        types.append("Synchro")
    if card_type & TYPE_XYZ:
        types.append("XYZ")
    if card_type & TYPE_LINK:
        types.append("Link")
    if card_type & TYPE_PENDULUM:
        types.append("Pendulum")
    return "/".join(types) if types else "Normal"
