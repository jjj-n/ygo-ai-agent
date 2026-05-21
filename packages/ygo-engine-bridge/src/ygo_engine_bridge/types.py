"""Type definitions for YGO Engine Bridge."""

from enum import Enum, IntEnum


class Phase(str, Enum):
    DRAW = "draw"
    STANDBY = "standby"
    MAIN1 = "main_phase_1"
    BATTLE_START = "battle_start"
    BATTLE_STEP = "battle_step"
    DAMAGE = "damage"
    DAMAGE_STEP = "damage_step"
    MAIN2 = "main_phase_2"
    END = "end"


class CardType(IntEnum):
    MONSTER = 0x1
    SPELL = 0x2
    TRAP = 0x4
    NORMAL = 0x10
    EFFECT = 0x20
    FUSION = 0x40
    RITUAL = 0x80
    TRAPMONSTER = 0x100
    SPIRIT = 0x200
    UNION = 0x400
    GEMINI = 0x800
    TUNER = 0x1000
    SYNCHRO = 0x2000
    TOKEN = 0x4000
    MAXIMUM = 0x8000
    QUICKPLAY = 0x10000
    CONTINUOUS = 0x20000
    EQUIP = 0x40000
    FIELD = 0x80000
    COUNTER = 0x100000
    Flip = 0x200000
    TOON = 0x400000
    XYZ = 0x800000
    PENDULUM = 0x1000000
    SPSUMMON = 0x2000000
    LINK = 0x4000000


class CardPosition(str, Enum):
    FACEUP_ATTACK = "faceup_attack"
    FACEDOWN_ATTACK = "facedown_attack"
    FACEUP_DEFENSE = "faceup_defense"
    FACEDOWN_DEFENSE = "facedown_defense"


class MoveType(str, Enum):
    SUMMON = "summon"
    SPECIAL_SUMMON = "special_summon"
    ACTIVATE_EFFECT = "activate_effect"
    SET_SPELL = "set_spell"
    SET_TRAP = "set_trap"
    CHANGE_POSITION = "change_position"
    TRIBUTE = "tribute"
    FUSION = "fusion"
    SYNCHRO = "synchro"
    XYZ = "xyz"
    LINK = "link"
    PENDULUM = "pendulum"
    DRAW = "draw"
    PHASE_END = "phase_end"
    ATTACK = "attack"


class Zone(str, Enum):
    DECK = "deck"
    HAND = "hand"
    MONSTER = "monster"
    SPELL_TRAP = "spell_trap"
    GRAVEYARD = "graveyard"
    BANISHED = "banished"
    EXTRA = "extra"
    FIELD_SPELL = "field_spell"


class Attribute(IntEnum):
    EARTH = 0x1
    WATER = 0x2
    FIRE = 0x4
    WIND = 0x8
    LIGHT = 0x10
    DARK = 0x20
    DIVINE = 0x40


class Race(IntEnum):
    WARRIOR = 0x1
    SPELLCASTER = 0x2
    FAIRY = 0x4
    FIEND = 0x8
    ZOMBIE = 0x10
    MACHINE = 0x20
    AQUA = 0x40
    PYRO = 0x80
    ROCK = 0x100
    WINGEDBEAST = 0x200
    PLANT = 0x400
    INSECT = 0x800
    THUNDER = 0x1000
    DRAGON = 0x2000
    BEAST = 0x4000
    BEASTWARRIOR = 0x8000
    DINOSAUR = 0x10000
    FISH = 0x20000
    SEASERPENT = 0x40000
    REPTILE = 0x80000
    PSYCHIC = 0x100000
    DIVINEBEAST = 0x200000
    CREATORGOD = 0x400000
    WYRM = 0x800000
    CYBERSE = 0x1000000
    ILLUSION = 0x2000000
    CYBORG = 0x4000000


# OCG Location constants
LOCATION_DECK = 0x01
LOCATION_HAND = 0x02
LOCATION_MZONE = 0x04
LOCATION_SZONE = 0x08
LOCATION_GRAVE = 0x10
LOCATION_REMOVED = 0x20
LOCATION_EXTRA = 0x40

# OCG Position constants
POS_FACEUP_ATTACK = 0x1
POS_FACEDOWN_ATTACK = 0x2
POS_FACEUP_DEFENSE = 0x4
POS_FACEDOWN_DEFENSE = 0x8

# Duel status
DUEL_STATUS_END = 0
DUEL_STATUS_AWAITING = 1
DUEL_STATUS_CONTINUE = 2
