"""Tool: get_card_info - Get detailed card information from database."""

from __future__ import annotations
import os
from typing import Optional
from pathlib import Path
from ygo_engine_bridge.cards import CardDatabase
from ygo_engine_bridge.process import _DEFAULT_CARD_DB
from ygo_engine_bridge.card_names_zh import get_card_id_by_chinese_name, search_chinese_names

# Chinese card database path
_DEFAULT_ZH_CARD_DB = Path(_DEFAULT_CARD_DB).parent / "cards_zh.cdb"

# Global card database instance
_card_db: Optional[CardDatabase] = None


def _get_card_db() -> CardDatabase:
    """Get or create card database connection."""
    global _card_db
    if _card_db is None:
        db_path = os.environ.get("CARD_DB_PATH", str(_DEFAULT_CARD_DB))
        zh_path = str(_DEFAULT_ZH_CARD_DB) if _DEFAULT_ZH_CARD_DB.exists() else None
        _card_db = CardDatabase(db_path, zh_db_path=zh_path)
        _card_db.connect()
    return _card_db


async def get_card_info(
    card_id: Optional[int] = None,
    card_name: Optional[str] = None,
) -> dict:
    """获取卡牌完整信息（效果/调整/适用规则）。

    可以通过卡牌 ID 或卡名查询。
    返回卡牌的完整效果文本、属性、种族等信息。
    支持中英文卡名查询。

    Args:
        card_id: 卡牌数据库 ID (与 card_name 二选一)
        card_name: 卡牌名称 (与 card_id 二选一)，支持中文和英文

    Returns:
        卡牌详细信息
    """
    if card_id is None and card_name is None:
        return {
            "success": False,
            "error": "Must provide either card_id or card_name",
        }

    try:
        db = _get_card_db()

        if card_id is not None:
            card_data = db.get_card(card_id)
            if card_data is None:
                return {
                    "success": False,
                    "error": f"Card not found with ID: {card_id}",
                }
            return {
                "success": True,
                "card": card_data,
            }

        if card_name is not None:
            # First try Chinese name lookup
            zh_card_id = get_card_id_by_chinese_name(card_name)
            if zh_card_id is not None:
                card_data = db.get_card(zh_card_id)
                if card_data:
                    # Add Chinese name to the result
                    card_data["name_zh"] = card_name
                    return {
                        "success": True,
                        "card": card_data,
                    }

            # Try Chinese name partial search
            zh_results = search_chinese_names(card_name, limit=5)
            if zh_results:
                # Get full card data for each result
                full_results = []
                for zh_card in zh_results:
                    card_data = db.get_card(zh_card["id"])
                    if card_data:
                        card_data["name_zh"] = zh_card["name"]
                        full_results.append(card_data)
                if full_results:
                    return {
                        "success": True,
                        "cards": full_results,
                        "count": len(full_results),
                    }

            # Fall back to English name search
            results = db.search_cards(card_name, limit=5)
            if not results:
                return {
                    "success": False,
                    "error": f"No cards found matching: {card_name}",
                }
            return {
                "success": True,
                "cards": results,
                "count": len(results),
            }

    except FileNotFoundError as e:
        return {
            "success": False,
            "error": f"Card database not found: {e}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
