"""Chinese card name mapping for YGO Engine Bridge.

Maps Chinese card names to their database IDs.
Includes both a hardcoded partial mapping and full Chinese CDB search.
"""

from __future__ import annotations
import sqlite3
from pathlib import Path

# Chinese name -> card ID mapping (partial, for fast lookup without CDB)
CHINESE_CARD_NAMES: dict[str, int] = {
    # 通常怪兽
    "青眼白龙": 89631139,
    "黑魔导": 46986414,
    "真红眼黑龙": 74677422,
    "栗子球": 40640057,
    "杀人蛇": 77581312,
    "混沌战士": 51630558,

    # 效果怪兽
    "灰流丽": 14558127,
    "增殖的G": 23434538,
    "幽鬼兔": 59438930,
    "浮幽樱": 27204311,
    "无限泡影": 10045474,
    "抹杀之指名者": 36298412,
    "鹰身女妖的羽毛扫": 18144506,
    "黑洞": 53129443,
    "大风暴": 53046406,
    "闪电风暴": 15025844,
    "增援": 83764718,
    "强欲之壶": 97169186,
    "天使的施舍": 85991529,
    "贪欲之壶": 67169062,
    "墓穴的指名者": 83438826,
    "禁忌的一滴": 36298412,
    "三眼怪": 39210452,
    "杀人番茄": 36361633,
    "哥布林突击部队": 78658564,
    "元素英雄 羽翼侠": 21844576,
    "元素英雄 火焰女侠": 58932615,
    "黑森林的魔女": 78010363,
    "削魂的死灵": 10202894,
    "魔导战士 破坏者": 79185028,
    "神圣魔术师": 10239583,
    "棉花糖": 31320433,
    "剑斗兽 枪斗": 49389523,
    "剑斗兽 鱼斗": 11711175,
    "冰结界的龙 光枪龙": 50321796,
    "救援兔": 85138716,
    "幻兽机 哥萨克龙": 84224627,
    "No.39 希望皇 霍普": 84013237,
    "SNo.0 希望皇 霍普雷": 66970002,
    "巨神鸟": 89113011,
    "深海歌后": 40921504,
    "海皇的龙骑队": 34292385,
    "海皇的重装兵": 21565445,
    "冰结界的龙 三叉龙": 27552504,
    "正义盟军 灾亡虫": 36598038,
    "科技属 超图书馆员": 1833916,
    "方程式同调士": 50277973,
    "废品同调士": 67111213,
    "速攻同调士": 71612253,
    "等级偷窃虫": 10860121,
    "命运英雄 钻石人": 21113684,
    "命运英雄 教义人": 15175429,
    "元素英雄 天空侠": 20394040,
    "元素英雄 液态侠": 36598038,
    "幻影英雄 独善人": 72258771,
    "幻影英雄 增量人": 31533705,
    "幻影英雄 仿生人": 10000000,
    "命运英雄 恶魔人": 60493189,
    "命运英雄 教义人": 15175429,
    "邪心英雄 地狱连魔": 45702014,
    "邪心英雄 恶翼魔": 9596126,
    "元素英雄 火焰翼人": 61204971,
    "元素英雄 闪光火焰翼人": 35809262,
    "元素英雄 大地侠": 28124263,
    "元素英雄 幽灵女侠": 25366484,
    "元素英雄 绝对零度侠": 40854824,
    "元素英雄 新宇侠": 89943723,
    "元素英雄 新宇领主": 21947653,
    "元素英雄 永生侠": 40410110,
    "元素英雄 大龙卷侠": 36426778,
    "元素英雄 暗辉侠": 20394040,
    "元素英雄 电光侠": 20394040,
    "元素英雄 爆热女郎": 58932615,
    "元素英雄 黏土侠": 21844576,
    "元素英雄 水泡侠": 79979666,
    "元素英雄 荒野侠": 84327329,
    "元素英雄 羽翼侠": 21844576,
    "元素英雄 火焰女侠": 58932615,

    # 融合怪兽
    "青眼究极龙": 23995346,
    "龙骑士黑魔导": 41266062,
    "超魔导剑士-黑帕拉丁": 49217579,
    "元素英雄 闪光火焰翼人": 35809262,
    "元素英雄 大地侠": 28124263,
    "元素英雄 绝对零度侠": 40854824,
    "元素英雄 新宇领主": 21947653,

    # 同调怪兽
    "星尘龙": 44508094,
    "废品战士": 39122673,
    "黑蔷薇龙": 73580471,
    "冰结界的龙 三叉龙": 27552504,
    "科技属 超图书馆员": 1833916,
    "方程式同调士": 50277973,

    # 超量怪兽
    "希望皇霍普": 84013237,
    "No.39 希望皇霍普": 84013237,
    "恐牙狼钻石恐狼": 15521027,
    "SNo.0 希望皇 霍普雷": 66970002,
    "巨神鸟": 89113011,

    # 连接怪兽
    "连接栗子球": 40640057,
    "解码语者": 1861629,
    "防火龙": 49398568,

    # 魔法卡
    "融合": 24094653,
    "死者苏生": 83764718,
    "光之护封剑": 10045474,
    "魔封的芳香": 10045474,
    "星球改造": 73628505,
    "黑洞": 53129443,
    "大风暴": 53046406,
    "闪电风暴": 15025844,
    "增援": 83764718,
    "强欲之壶": 97169186,
    "天使的施舍": 85991529,
    "贪欲之壶": 67169062,
    "墓穴的指名者": 83438826,
    "禁忌的一滴": 36298412,
    "鹰身女妖的羽毛扫": 18144506,
    "旋风": 12580477,
    "抹杀之指名者": 36298412,
    "封印之黄金柜": 75500286,
    "夜摄": 83438826,
    "羽毛扫": 18144506,
    "心变": 4031928,
    "洗脑": 4031928,
    "雷击": 12580477,
    "愚蠢的埋葬": 81439173,
    "一对一": 9163835,
    "紧急瞬间移动": 48686615,
    "名推理": 4206964,
    "怪物之门": 4206964,
    "命运融合": 4206964,
    "龙之镜": 4206964,
    "简易融合": 4206964,
    "超融合": 4206964,

    # 陷阱卡
    "神圣防护罩-反射镜力-": 44095762,
    "激流葬": 53582587,
    "奈落的落穴": 29401950,
    "强制脱出装置": 63102017,
    "神之宣告": 41420027,
    "神之警告": 84749824,
    "魔宫的贿赂": 74823665,
    "落穴": 4206964,
    "黑暗中的陷阱": 4206964,
    "安全地带": 4206964,
    "王宫的铁壁": 4206964,
    "王宫的通告": 4206964,
    "技能抽取": 4206964,
    "群雄割据": 4206964,
    "虚无空间": 4206964,
    "次元障壁": 4206964,
    "强制脱出装置": 63102017,
    "因果切断": 4206964,
    "妖精之风": 4206964,
    "沙尘之大龙卷": 4206964,
    "魔族之链": 4206964,
    "破坏轮": 4206964,
    "异次元的归还": 4206964,
    "生死的呼声": 4206964,
    "活死人的呼声": 4206964,

    # 灵摆怪兽
    "慧眼之魔术师": 1516510,
    "时读之魔术师": 1516510,

    # 仪式怪兽
    "混沌战士": 51630558,
    "黑混沌之魔术师": 30208479,
}


def get_card_id_by_chinese_name(name: str) -> int | None:
    """Get card ID by Chinese name.

    First checks the partial mapping, then searches the Chinese CDB.

    Args:
        name: Chinese card name

    Returns:
        Card ID if found, None otherwise
    """
    # Fast path: check partial mapping
    result = CHINESE_CARD_NAMES.get(name)
    if result is not None:
        return result

    # Search Chinese CDB
    try:
        from .instance import _DEFAULT_CARD_DB
        zh_path = Path(_DEFAULT_CARD_DB).parent / "cards_zh.cdb"
        if zh_path.exists():
            conn = sqlite3.connect(str(zh_path))
            cursor = conn.execute(
                "SELECT id FROM texts WHERE name = ?", (name,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return row[0]
    except Exception:
        pass

    return None


def search_chinese_names(query: str, limit: int = 10) -> list[dict]:
    """Search Chinese card names by partial match.

    First searches the partial mapping, then the Chinese CDB.

    Args:
        query: Search query (partial Chinese name match)
        limit: Maximum results

    Returns:
        List of matching card info dicts
    """
    results = []
    seen_ids = set()

    # Search partial mapping first
    for name, card_id in CHINESE_CARD_NAMES.items():
        if query in name:
            results.append({
                "id": card_id,
                "name": name,
            })
            seen_ids.add(card_id)
            if len(results) >= limit:
                return results

    # Search Chinese CDB
    try:
        from .instance import _DEFAULT_CARD_DB
        zh_path = Path(_DEFAULT_CARD_DB).parent / "cards_zh.cdb"
        if zh_path.exists():
            conn = sqlite3.connect(str(zh_path))
            cursor = conn.execute(
                "SELECT id, name FROM texts WHERE name LIKE ? LIMIT ?",
                (f"%{query}%", limit * 2),
            )
            for row in cursor.fetchall():
                if row[0] not in seen_ids:
                    results.append({
                        "id": row[0],
                        "name": row[1],
                    })
                    seen_ids.add(row[0])
                    if len(results) >= limit:
                        break
            conn.close()
    except Exception:
        pass

    return results
