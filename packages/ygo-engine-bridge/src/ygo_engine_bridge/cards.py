"""Card database queries for YGO Engine Bridge.

Reads card information from SQLite .cdb files.
Supports both English and Chinese card databases.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Optional

from .state import Card
from .types import CardType, Attribute, Race


class CardDatabase:
    """Query card information from a .cdb file.

    Supports optional Chinese database for bilingual card names.
    """

    def __init__(self, db_path: str, zh_db_path: Optional[str] = None):
        """Initialize with path to .cdb file.

        Args:
            db_path: Path to cards.cdb SQLite database (English)
            zh_db_path: Path to Chinese cards.cdb (optional)
        """
        self._db_path = db_path
        self._zh_db_path = zh_db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._zh_conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """Open database connections."""
        if not Path(self._db_path).exists():
            raise FileNotFoundError(f"Card database not found: {self._db_path}")
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row

        # Connect to Chinese database if available
        if self._zh_db_path and Path(self._zh_db_path).exists():
            try:
                self._zh_conn = sqlite3.connect(self._zh_db_path)
                self._zh_conn.row_factory = sqlite3.Row
            except Exception:
                self._zh_conn = None

    def close(self):
        """Close database connections."""
        if self._conn:
            self._conn.close()
            self._conn = None
        if self._zh_conn:
            self._zh_conn.close()
            self._zh_conn = None

    def _get_chinese_name(self, card_id: int) -> str:
        """Get Chinese name for a card from the Chinese database."""
        if not self._zh_conn:
            return ""
        try:
            cursor = self._zh_conn.execute(
                "SELECT name FROM texts WHERE id = ?", (card_id,)
            )
            row = cursor.fetchone()
            return row["name"] if row else ""
        except Exception:
            return ""

    def _get_chinese_desc(self, card_id: int) -> str:
        """Get Chinese description for a card from the Chinese database."""
        if not self._zh_conn:
            return ""
        try:
            cursor = self._zh_conn.execute(
                "SELECT desc FROM texts WHERE id = ?", (card_id,)
            )
            row = cursor.fetchone()
            return row["desc"] if row else ""
        except Exception:
            return ""

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

        # Add Chinese name and description if available
        zh_name = self._get_chinese_name(card_id)
        zh_desc = self._get_chinese_desc(card_id)
        if zh_name:
            result["name_zh"] = zh_name
        if zh_desc:
            result["desc_zh"] = zh_desc

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
        """Search cards by name (supports Chinese and English).

        Args:
            query: Search query (partial name match)
            limit: Maximum results

        Returns:
            List of card data dictionaries
        """
        if not self._conn:
            self.connect()

        results = []

        # First try Chinese name search if Chinese DB is available
        if self._zh_conn:
            try:
                cursor = self._zh_conn.execute(
                    "SELECT id, name FROM texts WHERE name LIKE ? LIMIT ?",
                    (f"%{query}%", limit),
                )
                zh_results = cursor.fetchall()
                for row in zh_results:
                    # Get full card data from English DB
                    card_data = self.get_card(row["id"])
                    if card_data:
                        results.append({
                            "id": card_data["id"],
                            "name": card_data["name"],
                            "name_zh": row["name"],
                            "type": card_data["type"],
                            "atk": card_data["atk"],
                            "def": card_data["def"],
                            "level": card_data["level"],
                        })
                        if len(results) >= limit:
                            return results
            except Exception:
                pass

        # Fall back to English name search
        try:
            cursor = self._conn.execute(
                "SELECT d.id, t.name, d.type, d.atk, d.def, d.level "
                "FROM datas d JOIN texts t ON d.id = t.id "
                "WHERE t.name LIKE ? LIMIT ?",
                (f"%{query}%", limit - len(results)),
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
                return results

        for row in cursor.fetchall():
            # Avoid duplicates
            if not any(r["id"] == row["id"] for r in results):
                zh_name = self._get_chinese_name(row["id"])
                results.append({
                    "id": row["id"],
                    "name": row["name"],
                    "name_zh": zh_name if zh_name else "",
                    "type": row["type"],
                    "atk": row["atk"],
                    "def": row["def"],
                    "level": row["level"],
                })

        return results

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
