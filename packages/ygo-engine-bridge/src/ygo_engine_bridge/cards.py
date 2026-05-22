"""Card database queries for YGO Engine Bridge.

Reads card information from SQLite .cdb files.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional

from .state import Card
from .types import CardType, Attribute, Race


class CardDatabase:
    """Query card information from a .cdb file."""

    def __init__(self, db_path: str):
        """Initialize with path to .cdb file.

        Args:
            db_path: Path to cards.cdb SQLite database
        """
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """Open database connection."""
        if not Path(self._db_path).exists():
            raise FileNotFoundError(f"Card database not found: {self._db_path}")
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def get_card(self, card_id: int) -> Optional[dict]:
        """Get card information by ID.

        Args:
            card_id: The card's database ID

        Returns:
            Card data dictionary or None if not found
        """
        if not self._conn:
            self.connect()

        cursor = self._conn.execute(
            "SELECT * FROM datas WHERE id = ?", (card_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Get card text (texts table may not exist in test CDBs)
        text_row = None
        try:
            cursor = self._conn.execute(
                "SELECT * FROM texts WHERE id = ?", (card_id,)
            )
            text_row = cursor.fetchone()
        except sqlite3.OperationalError:
            pass

        result = {
            "id": row["id"],
            "alias": row["alias"],
            "type": row["type"],
            "atk": row["atk"],
            "def": row["def"],
            "level": row["level"],
            "race": row["race"],
            "attribute": row["attribute"],
            "name": text_row["name"] if text_row else "",
            "desc": text_row["desc"] if text_row else "",
            "str1": text_row["str1"] if text_row else "",
            "str2": text_row["str2"] if text_row else "",
            "str3": text_row["str3"] if text_row else "",
            "str4": text_row["str4"] if text_row else "",
            "str5": text_row["str5"] if text_row else "",
            "str6": text_row["str6"] if text_row else "",
            "str7": text_row["str7"] if text_row else "",
            "str8": text_row["str8"] if text_row else "",
            "str9": text_row["str9"] if text_row else "",
            "str10": text_row["str10"] if text_row else "",
            "str11": text_row["str11"] if text_row else "",
            "str12": text_row["str12"] if text_row else "",
            "str13": text_row["str13"] if text_row else "",
            "str14": text_row["str14"] if text_row else "",
            "str15": text_row["str15"] if text_row else "",
            "str16": text_row["str16"] if text_row else "",
        }
        return result

    def get_card_as_model(self, card_id: int) -> Optional[Card]:
        """Get card as a Card model instance.

        Args:
            card_id: The card's database ID

        Returns:
            Card instance or None
        """
        data = self.get_card(card_id)
        if not data:
            return None

        return Card(
            card_id=data["id"],
            name=data["name"],
            card_type=CardType(data["type"]) if data["type"] else CardType.MONSTER,
            atk=data["atk"] if data["atk"] >= 0 else None,
            def_=data["def"] if data["def"] >= 0 else None,
            level=data["level"],
            attribute=Attribute(data["attribute"]) if data["attribute"] else None,
            race=Race(data["race"]) if data["race"] else None,
            effect_text=data["desc"],
        )

    def search_cards(self, query: str, limit: int = 10) -> list[dict]:
        """Search cards by name.

        Args:
            query: Search query (partial name match)
            limit: Maximum results

        Returns:
            List of card data dictionaries
        """
        if not self._conn:
            self.connect()

        try:
            cursor = self._conn.execute(
                "SELECT d.id, t.name, d.type, d.atk, d.def, d.level "
                "FROM datas d JOIN texts t ON d.id = t.id "
                "WHERE t.name LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            )
        except sqlite3.OperationalError:
            # texts table doesn't exist — search by ID only
            try:
                card_id = int(query)
                cursor = self._conn.execute(
                    "SELECT id, '' as name, type, atk, def, level FROM datas WHERE id = ?",
                    (card_id,),
                )
            except ValueError:
                return []

        return [
            {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "atk": row["atk"],
                "def": row["def"],
                "level": row["level"],
            }
            for row in cursor.fetchall()
        ]

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
