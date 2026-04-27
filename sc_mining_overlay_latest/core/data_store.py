
from __future__ import annotations

import json
from collections import Counter
import re
from pathlib import Path
from typing import Any

FAMILY = {
    "Arrowhead":"箭矢","Atzkav":"阿茲卡夫","Arclight":"弧光","Parallax":"視差","Karna":"卡納",
    "Coda":"科達","Custodian":"監護者","Deadrig":"亡裝","Devastator":"毀滅者","Fresnel":"菲涅耳",
    "Gallant":"加蘭特","Killshot":"絕殺","Pulverizer":"粉碎者","Quartz":"石英","Prism":"稜鏡",
    "Pulse":"脈衝","Tripledown":"三連擊","Yubarev":"尤巴列夫","Zenith":"天頂","Ripper":"開膛手",
    "Scalpel":"手術刀","Ravager-212":"掠奪者-212",
    "Antium":"安提姆","Artimex":"阿提米克斯","Argus":"阿古斯","Aril":"艾瑞爾","Aves":"艾維斯",
    "Badami":"巴達米","Calico":"卡利科","Carnifex":"屠戮者","Citadel":"城塞","Corbel":"科貝爾",
    "Dust Devil":"塵魔","Fortifier":"防禦者","Morningstar":"晨星","Novikov":"諾維科夫",
    "Pembroke":"彭布羅克","Piecemeal":"拼裝","Xenotech":"異星科技",
    "Polaris":"北極星","Perseus":"珀爾修斯","Odyssey":"奧德賽","Pioneer":"拓荒者",
    "Hull C":"貨艙 C","Hull D":"貨艙 D","Hull E":"貨艙 E",
    "Carrack":"卡拉克","Reclaimer":"回收者","Vulture":"禿鷹","Prospector":"勘探者","MOLE":"鼴鼠",
    "Corsair":"海盜船","Cutlass":"弧刀","Avenger":"復仇者","Gladius":"角鬥士",
    "Sabre":"軍刀","Vanguard":"先鋒","Hammerhead":"錘頭鯊","Idris":"伊德里斯","Javelin":"標槍",
}
SPECIAL_FAMILY = {
    "TrueDef-Pro": "真防護",
    "Morozov-SH": "莫羅佐夫",
    "Arden-SL": "阿登",
    "Balor HCH": "巴洛爾",
    "Xenotech-X1": "異星科技",
}

CUSTOM_NAME_TRANSLATIONS = {
    "Fun Kopion Skull": "趣味科皮昂骷髏",
    "Fun Military Skull": "趣味軍武骷髏",
    "Ascension": "飛升",
    "Heatwave": "熱浪",
    "Cool Metal": "冷冽金屬",
}

VARIANT = {
    "Shock Trooper":"震擊兵","Black Op":"黑色行動","Crimson Camo":"深紅迷彩","Delta Camo":"三角洲迷彩",
    "Hemlock Camo":"鐵杉迷彩","Moss Camo":"苔蘚迷彩","ASD Edition":"ASD 版","Nightstalker":"夜行者",
    "Thunderstrike":"雷擊","Darkwave":"暗潮","Landslide":"山崩","Sunstone":"日曜石","Sanguine":"血紅",
    "Bonedust":"骨塵","Deep Sea":"深海","Firesteel":"烈鋼","Blacklist":"黑名單","Deadfall":"墜林",
    "Scorched":"焦痕","Righteous":"正義","Kismet":"天命","Igniter":"點火","Mirage":"幻影",
    "Herrero":"赫雷羅","Midnight":"午夜","Stormfall":"風暴墜落","Warhawk":"戰鷹","Icebox":"冰匣",
    "Molten":"熔火","Rockfall":"落岩","Brimstone":"硫火","Fate":"宿命","Rager":"怒者","Valor":"英勇",
    "Sunblock":"遮陽","Lumen":"流明","Rouge":"胭紅","Canuto":"卡努托","Lodestone":"磁石",
    "Wildwood":"荒木","Tactical":"戰術型","Halcyon":"寧和","Mire":"泥沼","Patina":"銅綠",
    "Smolder":"餘燼","Desert Shadow":"沙影","Desert":"沙漠","Forest":"森林","Rogue":"浪人",
    "Whiteout":"白障","Jet":"墨黑","Maroon":"栗紅","Sand":"沙色","Storm":"風暴",
    "Daimyo":"大名","Icefall":"冰瀑","Woodland":"林地","Supernova":"超新星","Daystar":"晨星",
    "Metropolis":"都會","Moonfall":"月落","Shooting Star":"流星","Clanguard":"衛疆",
    "Combustion":"燃燒","Earthshake":"震地","Nightveil":"夜幕","Turfwar":"地盤戰","Modified":"改",
}
TYPE = {
    "Laser Sniper Rifle":"雷射狙擊步槍","Energy Assault Rifle":"能量突擊步槍","Energy LMG":"能量輕機槍",
    "Energy SMG":"能量衝鋒槍","Laser Shotgun":"雷射霰彈槍","Sniper Rifle":"狙擊步槍",
    "Twin Shotgun":"雙管霰彈槍","Shotgun":"霰彈槍","Pistol":"手槍","Rifle":"步槍","SMG":"衝鋒槍",
    "LMG":"輕機槍","Railgun":"磁軌炮","Grenade Launcher":"榴彈發射器",
}
PART = {
    "Exploration Suit":"探索服","Armor Arms":"臂甲","Armor Core":"護甲 核心","Armor Legs":"腿甲",
    "Battery":"電池","Magazine":"彈匣","Helmet":"頭盔","Arms":"臂甲","Core":"核心","Legs":"腿部",
    "Armor":"護甲","Base":"模組","Quantum Drive":"量子引擎","Shield":"護盾","Power Plant":"電源",
    "Cooler":"冷卻器","Radar":"雷達",
}

LOCATION_TRANSLATIONS = {
    "Lorville": "羅威爾",
    "Everus Harbor": "永恆港",
    "Grim HEX": "格林 HEX",
    "Crusader corridor": "十字軍航廊",
    "ArcCorp corridor": "弧光星航廊",
    "Hurston corridor": "赫斯頓航廊",
    "Klescher Rehabilitation Facility": "克雷舍改造設施",
    "The Grove": "樹林區",
    "Boondoggle": "荒行地",
    "HDMS-Norgaard": "HDMS-諾爾加德",
    "HDMS-Anderson": "HDMS-安德森",
    "HDMO-Dobbs": "HDMO-多布斯",
    "Aaron Halo": "亞倫光環",
    "Aaron Halo Belt": "亞倫光環帶",
    "C-Type asteroid fields": "C型小行星區",
    "E-Type asteroid fields": "E型小行星區",
    "I-Type asteroid fields": "I型小行星區",
    "M-Type asteroid fields": "M型小行星區",
    "P-Type asteroid fields": "P型小行星區",
    "Q-Type asteroid fields": "Q型小行星區",
    "S-Type asteroid fields": "S型小行星區",
    "multi-system": "多星系",
    "CRU-L2": "CRU-L2",
    "ArcCorp": "弧光星",
    "Crusader": "十字軍",
    "Hurston": "赫斯頓",
    "Daymar": "戴瑪",
    "Aberdeen": "阿伯丁",
}

CODE_PREFIXES = {
    "A03","ADP","ADP-mk4","BR-2","C54","F55","FS-9","LH86","P6-LR","P8-AR","P8-SC","R97","S71",
    "CBH-3","G-2","ORC-mkV","ORC-mkX","PAB-1","TrueDef-Pro","Morozov-SH","Arden-SL","Balor HCH","Xenotech-X1"
}


class MiningDataStore:
    def __init__(self, json_path: Path) -> None:
        self.json_path = json_path
        self.payload = self._load(json_path)
        self._sccrafter = self._load_sccrafter_index()
        self._body_name_map = self._build_body_name_map(self.payload)
        self._mineral_map, self._resource_alias_map = self._build_resource_maps(self.payload, self._sccrafter)
        self._bodies = self._flatten_bodies(self.payload)
        self._by_id = {item["id"]: item for item in self._bodies}
        self._resources_master = self.payload.get("resources_master", [])
        self._ship_asteroid_profiles = self._build_ship_asteroid_profiles(self.payload)
        self._resource_master_index = self._build_resource_master_index()
        self._blueprints = self.payload.get("blueprints", [])
        self._scc_items = self._sccrafter.get("items", [])
        self._scc_materials_master = self._sccrafter.get("materials_master", [])
        self._mission_translation_map = self._sccrafter.get("mission_translation_map", {})
        self._facility_guides = self.payload.get("facility_guides", [])

    @staticmethod
    def _load(path: Path) -> dict[str, Any]:
        default_payload = {
            "systems": [],
            "resources_master": [],
            "blueprints": [],
            "facility_guides": [],
        }
        if not path.exists():
            return default_payload
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            return payload if isinstance(payload, dict) else default_payload
        except Exception:
            return default_payload

    @staticmethod
    def _flatten_bodies(payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for system in payload.get("systems", []):
            system_name = system.get("name_en", "")
            system_name_zh = system.get("name_zh_tw", "")
            for body in system.get("bodies", []):
                rows.append({
                    "id": body.get("id", ""),
                    "system": system_name,
                    "system_zh": system_name_zh,
                    "name_en": body.get("name_en", ""),
                    "name_zh": body.get("name_zh_tw", ""),
                    "type": body.get("type", ""),
                    "parent": body.get("parent"),
                    "travel": body.get("travel", {}),
                    "mining": body.get("mining", {}),
                    "locations": body.get("locations", []),
                    "sources": body.get("sources", []),
                })
        return rows

    @staticmethod
    def _build_body_name_map(payload: dict[str, Any]) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for system in payload.get("systems", []):
            sys_en = (system.get("name_en") or "").strip()
            sys_zh = (system.get("name_zh_tw") or "").strip()
            if sys_en and sys_zh:
                mapping[sys_en.lower()] = sys_zh
            for body in system.get("bodies", []):
                en = (body.get("name_en") or "").strip()
                zh = (body.get("name_zh_tw") or "").strip()
                if en and zh:
                    mapping[en.lower()] = zh
        return mapping

    @staticmethod
    def _build_resource_maps(payload: dict[str, Any], sccrafter: dict[str, Any] | None = None) -> tuple[dict[str, str], dict[str, list[str]]]:
        mineral_map = {
            "quantanium": "量子礦","taranite": "塔拉奈特","bexalite": "貝克斯礦","gold": "黃金","diamond": "鑽石",
            "copper": "銅","tungsten": "鎢","aluminum": "鋁","corundum": "剛玉","titanium": "鈦","borase": "硼石",
            "laranite": "拉拉奈特","agricium": "農金屬","beryl": "綠柱石","quartz": "石英","inert materials": "惰性材料",
            "stileron": "稀鈦鐵","iron": "鐵","silicon": "矽","nickel": "鎳","helium": "氦","hassium": "𨧀",
            "gneiss": "片麻岩","rutile": "金紅石","hematite": "赤鐵礦","felsic": "長英質","hephaestanite": "赫菲斯坦石",
            "aphorite": "阿佛石","dolivine": "多利文石","hadanite": "哈丹石","janalite": "加納石","carinite": "科力晶",
            "carinite (pure)": "純科力晶","beradom": "貝拉多姆","feynmaline": "熵瞬晶","glacosite": "冰磧棉",
            "jaclium": "賈克利姆","jaclium (ore)": "賈克利姆原礦","saldynium": "薩爾迪銦","saldynium (ore)": "薩爾迪銦原礦",
            "riccite": "鈺石","aslarite": "阿斯拉石","lindinium": "林迪鎳",
            "carbon": "碳","ice": "冰","tin": "錫","ouratite": "歐拉礦","saldyniumore": "薩爾迪銦原礦",
        }
        alias_map: dict[str, list[str]] = {"iron": ["鐵"], "carinite": ["科力晶"], "carinite (pure)": ["純科力晶"]}

        def add_resource(en_name: str | None, zh_name: str | None, aliases: list[str] | None = None) -> None:
            en = (en_name or "").strip()
            zh = (zh_name or "").strip()
            if not en:
                return
            key = en.lower()
            if zh:
                mineral_map[key] = zh
            alias_map.setdefault(key, []).append(en)
            if zh:
                alias_map[key].append(zh)
            for alias in aliases or []:
                alias_text = str(alias).strip()
                if alias_text:
                    alias_map[key].append(alias_text)
            compact = re.sub(r"[^a-z0-9]+", "", key)
            if compact and compact != key:
                alias_map[key].append(compact)

        for rm in payload.get("resources_master", []):
            add_resource(rm.get("name_en"), rm.get("name_zh_tw"), list(rm.get("aliases") or []))

        sccrafter = sccrafter or {}
        for mat in sccrafter.get("materials_master", []) or []:
            add_resource(mat.get("name_en"), mat.get("name_zh_tw"), list(mat.get("aliases") or []))
        for item in sccrafter.get("items", []) or []:
            for mat in item.get("materials", []) or []:
                add_resource(mat.get("name_en"), mat.get("name_zh_tw") or mat.get("name_zh"), [])

        for en, zh in mineral_map.items():
            alias_map.setdefault(en, [])
            if zh not in alias_map[en]:
                alias_map[en].append(zh)
            if en not in alias_map[en]:
                alias_map[en].append(en)
        alias_map = {k: list(dict.fromkeys([x for x in v if x])) for k, v in alias_map.items()}
        return mineral_map, alias_map


    @staticmethod
    def _build_ship_asteroid_profiles(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        profiles: dict[str, dict[str, Any]] = {}
        ref = payload.get("ship_mining_reference") or {}
        for item in ref.get("asteroid_types", []) or []:
            type_name = str(item.get("type") or "").strip()
            if not type_name:
                continue
            key = f"{type_name} asteroid fields".lower()
            profiles[key] = item
        return profiles

    def _build_resource_master_index(self) -> dict[str, dict[str, Any]]:
        idx = {}
        for item in self._resources_master:
            keys = []
            for key in [item.get("name_en"), item.get("name_zh_tw")]:
                if key:
                    keys.append(str(key).strip().lower())
            for a in item.get("aliases") or []:
                if str(a).strip():
                    keys.append(str(a).strip().lower())
            for key in keys:
                idx[key] = item
        return idx

    def all_bodies(self) -> list[dict[str, Any]]:
        return list(self._bodies)

    def get_body(self, body_id: str) -> dict[str, Any] | None:
        return self._by_id.get(body_id)

    def get_meta(self) -> dict[str, Any]:
        return self.payload.get("meta", {})

    def get_body_zh(self, name: str | None) -> str | None:
        if not name:
            return None
        key = name.strip().lower()
        return self._body_name_map.get(key) or LOCATION_TRANSLATIONS.get(str(name).strip())

    def translate_resource_name(self, name: str | None) -> str | None:
        if not name:
            return None
        key = name.strip().lower()
        direct = self._mineral_map.get(key)
        if direct:
            return direct
        compact = re.sub(r"[^a-z0-9]+", "", key)
        if compact:
            for en, zh in self._mineral_map.items():
                if re.sub(r"[^a-z0-9]+", "", en) == compact:
                    return zh
        return None

    def bilingual_body(self, body_en: str | None, body_zh: str | None = None) -> str:
        zh = body_zh or self.get_body_zh(body_en)
        if zh and body_en:
            return f"{zh} / {body_en}"
        return zh or body_en or "-"

    def bilingual_location_name(self, name: str | None) -> str:
        if not name:
            return "-"
        raw = str(name).strip()
        zh = LOCATION_TRANSLATIONS.get(raw)
        if zh and zh != raw:
            return f"{zh} / {raw}"
        return raw

    def bilingual_resource(self, name_en: str | None, name_zh: str | None = None) -> str:
        zh = name_zh or self.translate_resource_name(name_en)
        if zh and name_en:
            return f"{zh} / {name_en}"
        return zh or name_en or "-"

    def _translate_english_item_name(self, name_en: str | None) -> str | None:
        if not name_en:
            return None
        s = str(name_en)
        replacements = {}
        replacements.update(CUSTOM_NAME_TRANSLATIONS)
        replacements.update(SPECIAL_FAMILY)
        replacements.update(FAMILY)
        replacements.update(VARIANT)
        replacements.update(TYPE)
        replacements.update(PART)
        for old, new in sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True):
            s = s.replace(old, new)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    def bilingual_blueprint(self, name_en: str | None, name_zh: str | None = None) -> str:
        disp_zh = name_zh
        if not disp_zh or disp_zh == name_en:
            disp_zh = self._translate_english_item_name(name_en)
        if disp_zh and name_en and disp_zh != name_en:
            return f"{disp_zh} / {name_en}"
        return disp_zh or name_en or "-"

    def extract_resource_terms(self, text: str) -> list[str]:
        if not text:
            return []
        terms = [text]
        match = re.match(r"([A-Za-z][A-Za-z'() -]+)", text)
        if match:
            name_en = match.group(1).strip()
            zh = self.translate_resource_name(name_en)
            if zh:
                terms.append(zh)
            for alias in self._resource_alias_map.get(name_en.lower(), []):
                if alias:
                    terms.append(alias)
        return list(dict.fromkeys(t for t in terms if t))

    def translate_resource_text(self, text: str) -> str:
        if not text:
            return "-"
        match = re.match(r"([A-Za-z][A-Za-z'() -]+)", text)
        if not match:
            return text
        name_en = match.group(1).strip()
        zh = self.translate_resource_name(name_en)
        if not zh:
            return text
        remainder = text[len(match.group(1)):]
        return f"{zh} / {name_en}{remainder}" if remainder else f"{zh} / {name_en}"

    def translate_known_text(self, text: str) -> str:
        if not text:
            return "-"
        output = text
        for en, zh in sorted(self._body_name_map.items(), key=lambda x: len(x[0]), reverse=True):
            output = re.sub(rf"\\b{re.escape(en)}\\b", zh, output, flags=re.IGNORECASE)
        for en, zh in sorted(self._mineral_map.items(), key=lambda x: len(x[0]), reverse=True):
            output = re.sub(rf"\\b{re.escape(en)}\\b", zh, output, flags=re.IGNORECASE)
        output = output.replace("hathor orbital laser platforms", "哈梭爾軌道雷射平台")
        return output

    def bilingualize_known_text(self, text: str) -> str:
        if not text:
            return "-"
        output = str(text)

        phrase_pairs = [
            ("hathor orbital laser platforms", "哈梭爾軌道雷射平台 / Hathor orbital laser platforms"),
            ("collection_contract", "收集合約 / collection_contract"),
            ("mercenary", "傭兵任務 / mercenary"),
            ("delivery", "送貨任務 / delivery"),
            ("Jump to ", "跳轉至 "),
            (" then quantum to ", "，再量子跳躍至 "),
            (" marker.", " 標記點。"),
            ("Use a long quantum route and cut the jump early into the belt.", "使用長距離量子航線，並在進入帶區前提早切斷量子跳躍。"),
            ("Known reference cuts:", "常見參考切點："),
            ("Very hot environment; bring protection. Strong ROC route body.", "環境高溫，需攜帶防護裝備。是強勢 ROC 採集區域。"),
            ("Widely described as one of", "普遍被視為"),
            ("most valuable mining areas.", "最有價值的採礦區之一。"),
            ("Contains several high-value ores; some community guides also claim ", "包含多種高價礦物；部分社群指南也認為 "),
            (" routes here, though that conflicts with the currently accessible wiki mineral list.", " 在此有採集路線，但這與目前可取得的 wiki 礦物清單有衝突。"),
            ("Community 4.6 guide says ", "社群 4.6 指南指出 "),
            (" is the best ", " 是最佳的 "),
            ("Multiple sources tie ", "多個來源指出 "),
            (" and gem-focused ROC routes.", " 與以寶石為主的 ROC 路線有關。"),
            ("Pure ", "純"),
        ]
        for en, bi in phrase_pairs:
            output = re.sub(re.escape(en), bi, output, flags=re.IGNORECASE)

        for en, zh in sorted(LOCATION_TRANSLATIONS.items(), key=lambda x: len(x[0]), reverse=True):
            if zh != en:
                output = re.sub(rf"\b{re.escape(en)}\b", f"{zh} / {en}", output)

        for en, zh in sorted(self._body_name_map.items(), key=lambda x: len(x[0]), reverse=True):
            en_disp = en.title() if en.islower() else en
            output = re.sub(rf"\b{re.escape(en)}\b", f"{zh} / {en_disp}", output, flags=re.IGNORECASE)

        for en, zh in sorted(self._mineral_map.items(), key=lambda x: len(x[0]), reverse=True):
            en_disp = en.title() if en.islower() else en
            output = re.sub(rf"\b{re.escape(en)}\b", f"{zh} / {en_disp}", output, flags=re.IGNORECASE)

        # dedupe repeated bilingual place names
        output = re.sub(r"([\u4e00-\u9fff]+)\s+\1\s*/\s*([A-Za-z][A-Za-z0-9 .()\-]+)", r"\1 / \2", output)
        output = re.sub(r"([\u4e00-\u9fff]+)\s*/\s*\1\s*/\s*([A-Za-z][A-Za-z0-9 .()\-]+)", r"\1 / \2", output)
        output = output.replace("阿伯丁 / 阿伯丁 / Aberdeen", "阿伯丁 / Aberdeen")
        output = output.replace("戴瑪 / 戴瑪 / Daymar", "戴瑪 / Daymar")
        output = output.replace("利里亞 / 利里亞 / Lyria", "利里亞 / Lyria")
        output = output.replace("赫斯頓 / 赫斯頓 / Hurston", "赫斯頓 / Hurston")
        output = output.replace("史丹頓 / 史丹頓 / Stanton", "史丹頓 / Stanton")
        output = output.replace("阿伯丁 / Aberdeen / 戴瑪 / Daymar", "阿伯丁 / Aberdeen 與 戴瑪 / Daymar")
        output = output.replace("戴瑪 / Daymar / 阿伯丁 / Aberdeen", "戴瑪 / Daymar 與 阿伯丁 / Aberdeen")
        output = output.replace("，，", "，")
        output = output.replace("to ", "")
        output = output.replace("body.", "區域。")
        return self._dedupe_lines(output)


    def _dedupe_lines(self, text: str) -> str:
        if not text:
            return "-"
        seen = set()
        out = []
        for raw in str(text).splitlines():
            line = raw.strip()
            if not line:
                if out and out[-1] != "":
                    out.append("")
                continue
            if line in seen:
                continue
            seen.add(line)
            out.append(line)
        while out and out[0] == "":
            out.pop(0)
        while out and out[-1] == "":
            out.pop()
        return "\n".join(out) if out else "-"

    def _display_zh(self, name: str | None) -> str | None:
        key = str(name or "").strip()
        if not key:
            return None
        return self.get_body_zh(key) or self._body_name_map.get(key.lower()) or LOCATION_TRANSLATIONS.get(key) or None

    def _render_known_location_line(self, loc: dict[str, Any]) -> str:
        body_en = loc.get("body")
        system_en = loc.get("system")
        mode = self.normalize_mode(loc.get("mode"))
        body_disp = self.bilingual_body(body_en, self._display_zh(body_en))
        system_disp = self.bilingual_body(system_en, self._display_zh(system_en))
        loc_line = f"- {body_disp}"
        if system_disp and system_disp != "-":
            loc_line += f"｜{system_disp}"
        if mode and mode != "-":
            loc_line += f"｜{mode}"
        return loc_line

    def normalize_mode(self, mode: str | None) -> str:
        if not mode:
            return "-"
        m = str(mode).strip().lower()
        mapping = {
            "ship": "船挖","roc": "ROC","hand": "手挖","cave": "洞穴","surface": "地表",
            "asteroid": "太空 / 小行星","asteroid_belt": "小行星帶","ship_generic_asteroid_profile": "通用小行星型譜",
            "cave_exposed_by_hathor_platform_rare": "雷射平台暴露洞穴（稀有）",
            "cave_exposed_by_hathor_platform": "雷射平台暴露洞穴",
            "collection_contract": "收集合約","delivery": "送貨任務","mercenary": "傭兵任務",
        }
        return mapping.get(m, str(mode))

    def normalize_profile_level(self, value: str | None) -> str:
        if value is None:
            return "待補"
        mapping = {
            "low": "低",
            "medium": "中",
            "medium_to_high": "中偏高",
            "high": "高",
            "unknown": "待補",
        }
        return mapping.get(str(value).strip().lower(), str(value))

    def is_generic_asteroid_field(self, name: str | None) -> bool:
        raw = str(name or "").strip().lower()
        return raw in self._ship_asteroid_profiles

    def get_generic_asteroid_profile(self, name: str | None) -> dict[str, Any] | None:
        raw = str(name or "").strip().lower()
        return self._ship_asteroid_profiles.get(raw)

    def generic_asteroid_profile_text(self, name: str | None) -> str:
        profile = self.get_generic_asteroid_profile(name)
        title = self.bilingual_location_name(name)
        lines = [f"【{title}】", "類型：通用小行星成分類型", "所屬：多星系 / multi-system", "採集模式：通用小行星型譜"]
        if not profile:
            lines.append("")
            lines.append("說明：")
            lines.append("此項目是小行星成分類型，不是固定航點或唯一地點。")
            return "\n".join(lines)
        lines.append("")
        lines.append("說明：")
        lines.append("此項目是小行星成分類型，不是固定地名；代表該資源常見於此類型小行星。")
        typical = profile.get("typical") or []
        trace = profile.get("trace") or []
        if typical:
            lines.append("")
            lines.append("典型礦物：")
            for x in typical:
                lines.append(f"- {self.bilingual_resource(x, self.translate_resource_name(x))}")
        if trace:
            lines.append("")
            lines.append("稀有／伴生礦物：")
            for x in trace:
                lines.append(f"- {self.bilingual_resource(x, self.translate_resource_name(x))}")
        if profile.get("resistance"):
            lines.append("")
            lines.append(f"抗性：{self.normalize_profile_level(profile.get('resistance'))}")
        if profile.get("instability"):
            lines.append(f"不穩定度：{self.normalize_profile_level(profile.get('instability'))}")
        if profile.get("special_note"):
            lines.append(f"補充：{self.bilingualize_known_text(str(profile.get('special_note')))}")
        return "\n".join(lines)

    def _load_sccrafter_index(self) -> dict[str, Any]:
        candidates = [
            self.json_path.parent / "sccrafter_index.json",
            self.json_path.parent / "data" / "sccrafter_index.json",
            self.json_path.parent.parent / "data" / "sccrafter_index.json",
        ]
        for path in candidates:
            if path.exists():
                try:
                    payload = json.loads(path.read_text(encoding="utf-8-sig"))
                    if isinstance(payload, dict):
                        return payload
                except Exception:
                    continue
        return {}

    @staticmethod
    def _norm_key(value: str | None) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def get_resource_by_name(self, query: str | None) -> dict[str, Any] | None:
        key = self._norm_key(query)
        if not key:
            return None
        for item in self._resources_master:
            names = [item.get("name_en"), item.get("name_zh_tw")] + list(item.get("aliases") or [])
            for name in names:
                if self._norm_key(name) == key:
                    return item
        return None

    def find_item_candidates(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        q = self._norm_key(query)
        if not q:
            return []
        generic_terms = {"圖紙", "藍圖", "blueprint", "blueprints", "craft", "crafting"}
        if q in {self._norm_key(x) for x in generic_terms}:
            items = sorted(
                self._scc_items,
                key=lambda x: (
                    str(x.get("category_zh_tw") or x.get("category_zh") or x.get("category_en") or ""),
                    str(x.get("name_zh_tw") or x.get("name_zh") or x.get("name_en") or ""),
                ),
            )
            return items[:limit]
        scored = []
        seen = set()
        for item in self._scc_items:
            tokens = [
                item.get("name_en"),
                item.get("name_zh_tw"),
                item.get("name_zh"),
                item.get("name_zh_source_tw"),
                item.get("name_zh_source"),
                item.get("category_zh_tw"),
                item.get("category_zh"),
            ]
            best = 0.0
            for token in tokens:
                t = self._norm_key(token)
                if not t:
                    continue
                if q == t:
                    best = max(best, 1.0)
                elif t.startswith(q):
                    best = max(best, 0.97)
                elif len(q) >= 2 and q in t:
                    best = max(best, 0.9)
            if best > 0:
                name = item.get("name_en") or ""
                if name in seen:
                    continue
                seen.add(name)
                scored.append((best, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [it for _, it in scored[:limit]]

    def scc_items_for_resource(self, resource_item: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
        targets = set()
        for x in [resource_item.get("name_en"), resource_item.get("name_zh_tw")] + list(resource_item.get("aliases") or []):
            if x:
                targets.add(self._norm_key(x))
        out = []
        seen = set()
        for item in self._scc_items:
            matched = False
            for mat in item.get("materials", []):
                if self._norm_key(mat.get("name_en")) in targets or self._norm_key(mat.get("name_zh_tw")) in targets:
                    matched = True
                    break
            if matched:
                name = item.get("name_en") or ""
                if name in seen:
                    continue
                seen.add(name)
                out.append(item)
                if len(out) >= limit:
                    break
        return out

    def scc_item_material_rows(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for mat in item.get("materials", []):
            res = self.get_resource_by_name(mat.get("name_en")) or self.get_resource_by_name(mat.get("name_zh_tw"))
            title = self.bilingual_resource(mat.get("name_en"), mat.get("name_zh_tw") or mat.get("name_zh")) if res or mat.get("name_en") else (mat.get("name_zh_tw") or "-")
            rows.append({
                "kind": "item_material",
                "title": title,
                "subtitle": f'×{int(mat.get("quantity") or 1)}',
                "resource_item": res,
                "material_en": mat.get("name_en"),
                "material_zh": mat.get("name_zh_tw"),
            })
        return rows

    def scc_item_detail_text(self, item: dict[str, Any]) -> str:
        lines = []
        lines.append(f'【{self.bilingual_blueprint(item.get("name_en"), item.get("name_zh_tw") or item.get("name_zh"))}】')
        lines.append(f'分類：{item.get("category_zh_tw") or item.get("category_en")}')
        lines.append(f'材料數：{len(item.get("materials", []))}')
        lines.append("")
        lines.append("材料：")
        for mat in item.get("materials", []):
            mdisp = self.bilingual_resource(mat.get("name_en"), mat.get("name_zh_tw") or mat.get("name_zh")) if self.get_resource_by_name(mat.get("name_en")) or self.get_resource_by_name(mat.get("name_zh_tw")) else self.bilingual_blueprint(mat.get("name_en"), mat.get("name_zh_tw") or mat.get("name_zh"))
            lines.append(f'  - {mdisp} ×{int(mat.get("quantity") or 1)}')
        lines.append("")
        lines.append(f'獲取任務數：{int(item.get("mission_count") or 0)}')
        if item.get("missions"):
            lines.append("獲取任務：")
            for mission in item.get("missions", []):
                zh = mission.get("name_zh_tw") or mission.get("name_zh") or self._mission_translation_map.get(mission.get("name_en") or "") or mission.get("name_en")
                en = mission.get("name_en") or ""
                if zh and en and zh != en:
                    lines.append(f'  - {zh} / {en}')
                else:
                    lines.append(f'  - {zh or en}')
        return "\n".join(lines)

    def normalize_type(self, kind: str | None) -> str:
        return {"ore": "礦石","gem": "寶石","crafting": "合成材料"}.get(str(kind or "").lower(), str(kind or "-"))

    def normalize_value_tier(self, tier: str | None) -> str:
        return {
            "very_high": "極高","high": "高","medium_high": "中高","medium": "中","medium_low": "中低","low": "低","watch": "關注",
        }.get(str(tier or "").lower(), str(tier or "-"))

    def find_resource_candidates(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        q = (query or "").strip().lower()
        if not q:
            return []
        scored = []
        seen = set()
        for item in self._resources_master:
            en = (item.get("name_en") or "").strip()
            zh = (item.get("name_zh_tw") or "").strip()
            aliases = [str(a).strip() for a in (item.get("aliases") or []) if str(a).strip()]
            tokens = [en, zh] + aliases
            best = 0.0
            for token in tokens:
                t = token.lower()
                if q == t:
                    best = max(best, 1.0)
                elif t.startswith(q):
                    best = max(best, 0.97)
                elif len(q) >= 2 and q in t:
                    best = max(best, 0.92)
            if best > 0:
                key = (en.lower(), zh.lower())
                if key in seen:
                    continue
                seen.add(key)
                scored.append((best, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def resource_locations(self, resource_item: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        seen = set()
        for loc in resource_item.get("known_locations", []) or []:
            body_en = (loc.get("body") or "").strip()
            system_en = (loc.get("system") or "").strip()
            mode = self.normalize_mode(loc.get("mode"))
            source = (loc.get("source") or "").strip()
            body_id = None
            body_label = self.bilingual_body(body_en, self._display_zh(body_en)) if body_en else body_en
            system_label = self.bilingual_body(system_en, self._display_zh(system_en)) if system_en else system_en
            for b in self._bodies:
                if body_en and body_en.lower() == b["name_en"].lower():
                    body_id = b["id"]
                    body_label = self.bilingual_body(b["name_en"], b["name_zh"])
                    system_label = self.bilingual_body(b["system"], b["system_zh"])
                    break
            key = ("known", body_label.lower(), system_label.lower(), mode.lower())
            if key in seen:
                continue
            seen.add(key)
            extra = {}
            if self.is_generic_asteroid_field(body_en):
                extra["kind"] = "generic_asteroid_profile"
                extra["details"] = self.generic_asteroid_profile_text(body_en)
                extra["subtitle"] = self.bilingual_location_name(system_en) if system_en else "多星系 / multi-system"
                extra["mode"] = "通用小行星型譜"
            results.append({
                "kind": extra.get("kind", "resource_location"),"title": body_label or "未指明地點","subtitle": extra.get("subtitle", system_label or "未指明星系"),
                "mode": extra.get("mode", mode),"source": source,"body_id": body_id,"details": extra.get("details"),
            })
        target_terms = set()
        for x in [resource_item.get("name_en"), resource_item.get("name_zh_tw")] + list(resource_item.get("aliases") or []):
            if x:
                target_terms.add(str(x).strip().lower())
        for body in self._bodies:
            mining = body.get("mining", {})
            matched_groups = []
            for group_name, group in [("地表", mining.get("known_surface_resources", [])),("洞穴", mining.get("known_cave_resources", [])),("太空／小行星", mining.get("known_asteroid_resources", []))]:
                found = []
                for item in group:
                    text = str(item)
                    terms = [t.lower() for t in self.extract_resource_terms(text)]
                    if target_terms.intersection(terms):
                        found.append(self.translate_resource_text(text))
                if found:
                    matched_groups.append((group_name, found))
            if matched_groups:
                key = ("body", body["id"])
                if key in seen:
                    continue
                seen.add(key)
                snippets = []
                for group_name, found in matched_groups:
                    snippets.append(f"{group_name}：" + "；".join(found[:3]))
                results.append({
                    "kind": "body","title": self.bilingual_body(body["name_en"], body["name_zh"]),
                    "subtitle": self.bilingual_body(body["system"], body["system_zh"]),"body_id": body["id"],
                    "source": "dataset body mapping","details": " | ".join(snippets),
                })
        return results

    def resource_blueprints(self, resource_item: dict[str, Any], limit: int = 50) -> list[dict[str, Any]]:
        return self.scc_items_for_resource(resource_item, limit=limit)

    def blueprint_summary_lines(self, blueprint: dict[str, Any]) -> list[str]:
        lines = []
        name = self.bilingual_blueprint(blueprint.get("name_en"), blueprint.get("name_zh_tw"))
        lines.append(f"- {name}")
        lines.append(f"  分類：{blueprint.get('category_zh_tw') or blueprint.get('category_en')}")
        if blueprint.get("materials"):
            lines.append("  材料：")
            for mat in blueprint.get("materials", []):
                res = self.get_resource_by_name(mat.get("name_en")) or self.get_resource_by_name(mat.get("name_zh_tw"))
                if res:
                    mdisp = self.bilingual_resource(mat.get("name_en"), mat.get("name_zh_tw") or mat.get("name_zh"))
                else:
                    mdisp = self.bilingual_blueprint(mat.get("name_en"), mat.get("name_zh_tw") or mat.get("name_zh"))
                lines.append(f"    - {mdisp} ×{int(mat.get('quantity') or 1)}")
        lines.append(f"  獲取任務數：{int(blueprint.get('mission_count') or 0)}")
        if blueprint.get("missions"):
            lines.append("  獲取任務：")
            for mission in blueprint.get("missions", []):
                zh = mission.get("name_zh_tw") or mission.get("name_zh") or self._mission_translation_map.get(mission.get("name_en") or "") or mission.get("name_en")
                en = mission.get("name_en") or ""
                if zh and en and zh != en:
                    lines.append(f"    - {zh} / {en}")
                else:
                    lines.append(f"    - {zh or en}")
        lines.append("")
        return lines

    def resource_summary_parts(self, blueprint: dict[str, Any]) -> list[str]:
        lines = []
        name = self.bilingual_blueprint(blueprint.get("name_en"), blueprint.get("name_zh_tw"))
        lines.append(f"- {name}")

        acq = blueprint.get("acquisition") or {}
        tags = acq.get("mission_type_tags") or []
        if tags:
            zh_tags = [self.normalize_mode(t) for t in tags]
            lines.append("  取得：" + " / ".join(zh_tags))

        material_lines = []
        for item in (blueprint.get("scraped_materials") or []):
            men = str(item.get("name_en") or "").strip()
            if not men or men.lower() == "wikelo favor":
                continue
            mzh = item.get("name_zh_tw")
            qty = int(item.get("quantity") or 1)
            if self.translate_resource_name(men):
                mdisp = self.bilingual_resource(men, mzh)
            else:
                mdisp = self.bilingual_blueprint(men, mzh)
            material_lines.append(f"    - {mdisp} ×{qty}")

        if material_lines:
            lines.append("  材料：")
            lines.extend(material_lines)

        lines.append("")
        return lines

    def resource_summary_parts(self, resource_item: dict[str, Any], include_positions: bool = True) -> tuple[str, str]:
        header_lines = []
        blueprint_lines = []

        zh = resource_item.get("name_zh_tw") or resource_item.get("name_en") or "-"
        en = resource_item.get("name_en") or "-"
        header_lines.append(f"【{zh} / {en}】")
        header_lines.append(f"類型：{self.normalize_type(resource_item.get('type'))}")
        modes = resource_item.get("mining_modes") or []
        if modes:
            header_lines.append("採集方式：" + " / ".join(self.normalize_mode(x) for x in modes))
        header_lines.append(f"價值等級：{self.normalize_value_tier(resource_item.get('value_tier'))}")

        notes = resource_item.get("notes")
        if notes:
            header_lines.append("")
            header_lines.append("說明：")
            header_lines.append(self._dedupe_lines(self.bilingualize_known_text(str(notes))))

        summary = resource_item.get("known_location_summary")
        if summary:
            header_lines.append("")
            header_lines.append("已知採集位置摘要：")
            header_lines.append(self._dedupe_lines(self.bilingualize_known_text(str(summary))))

        known_locs = resource_item.get("known_locations") or []
        if include_positions and known_locs and not summary:
            header_lines.append("")
            header_lines.append("已知位置：")
            seen_loc_lines = set()
            rendered_loc_lines = []
            for loc in known_locs:
                loc_line = self._render_known_location_line(loc)
                if loc_line in seen_loc_lines:
                    continue
                seen_loc_lines.add(loc_line)
                rendered_loc_lines.append(loc_line)
            for loc_line in rendered_loc_lines[:8]:
                header_lines.append(loc_line)

        craft = resource_item.get("crafting_watch") or {}
        if craft:
            header_lines.append("")
            header_lines.append("合成關聯：")
            status = str(craft.get("status") or "-")
            header_lines.append("狀態：" + {"watch": "關注", "confirmed": "已確認"}.get(status.lower(), status))
            count = craft.get("blueprint_count")
            if count is not None:
                header_lines.append(f"藍圖數量：{count}")

        bps = self.resource_blueprints(resource_item, limit=8)
        if bps:
            blueprint_lines.append("關聯製作圖紙：")
            blueprint_lines.append("")
            for bp in bps:
                blueprint_lines.extend(self.blueprint_summary_lines(bp))

        return "\n".join(header_lines), "\n".join(blueprint_lines)

    def find_facility_candidates(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        q = self._norm_key(query)
        if not q:
            return []
        generic_terms = {"設施", "facility", "facilities", "facilityguide", "機庫", "行政機庫", "爭奪區", "基地", "哨站"}
        if q in {self._norm_key(x) for x in generic_terms}:
            items = sorted(self._facility_guides, key=lambda x: (str(x.get("facility_type") or ""), str(x.get("name_zh_tw") or x.get("name_en") or "")))
            return items[:limit]

        scored = []
        seen = set()
        for item in self._facility_guides:
            tokens = [
                item.get("name_en"), item.get("name_zh_tw"), item.get("system"),
                item.get("body"), item.get("facility_type"), item.get("classification")
            ] + list(item.get("aliases") or [])
            best = 0.0
            for token in tokens:
                t = self._norm_key(token)
                if not t:
                    continue
                if q == t:
                    best = max(best, 1.0)
                elif t.startswith(q):
                    best = max(best, 0.97)
                elif len(q) >= 2 and q in t:
                    best = max(best, 0.9)
            if best > 0:
                name = item.get("name_en") or ""
                if name in seen:
                    continue
                seen.add(name)
                scored.append((best, item))
        scored.sort(key=lambda x: (x[0], str(x[1].get("name_zh_tw") or x[1].get("name_en") or "")), reverse=True)
        return [it for _, it in scored[:limit]]

    def bilingual_facility(self, name_en: str | None, name_zh_tw: str | None) -> str:
        en = str(name_en or "").strip()
        zh = str(name_zh_tw or "").strip()
        if zh and en and zh != en:
            return f"{zh} / {en}"
        return zh or en or "-"

    def facility_detail_text(self, facility: dict[str, Any]) -> str:
        lines = []
        lines.append(f'【{self.bilingual_facility(facility.get("name_en"), facility.get("name_zh_tw"))}】')
        lines.append(f'系統：{self.bilingual_body(facility.get("system"), self.get_body_zh(facility.get("system")))}')
        body = facility.get("body")
        lines.append(f'位置：{self.bilingual_location_name(self.bilingual_body(body, self.get_body_zh(body)) if body else "-")}')
        lines.append(f'設施類型：{facility.get("facility_type") or "-"}')
        lines.append(f'分類：{facility.get("classification") or "-"}')
        if facility.get("status"):
            lines.append(f'狀態：{facility.get("status")}')
        if facility.get("version_notes"):
            lines.append(f'版本：{self.bilingualize_known_text(facility.get("version_notes"))}')
        if facility.get("summary"):
            lines.append("")
            lines.append("摘要：")
            lines.append(self.bilingualize_known_text(facility.get("summary")))
        if facility.get("access"):
            lines.append("")
            lines.append("進入方式：")
            lines.append(self.bilingualize_known_text(facility.get("access")))
        if facility.get("guide"):
            lines.append("")
            lines.append("攻略：")
            lines.extend(self.bilingualize_known_text(facility.get("guide")).splitlines())
        if facility.get("card_locations"):
            lines.append("")
            lines.append("拿卡片位置：")
            for r in facility.get("card_locations", []):
                lines.append(f"- {self.bilingualize_known_text(str(r))}")
        if facility.get("timing"):
            lines.append("")
            lines.append("開啟時間：")
            lines.extend(self.bilingualize_known_text(facility.get("timing")).splitlines())
        if facility.get("rewards_summary"):
            lines.append("")
            lines.append("固定獎勵：")
            lines.append(self.bilingualize_known_text(facility.get("rewards_summary")))
        if facility.get("rewards"):
            lines.append("")
            lines.append("獎勵：")
            for r in facility.get("rewards", []):
                lines.append(f"- {self.bilingualize_known_text(str(r))}")
        if facility.get("external_tools"):
            lines.append("")
            lines.append("外部倒數：")
            for r in facility.get("external_tools", []):
                lines.append(f"- {self.bilingualize_known_text(str(r))}")
        if facility.get("diagram_text"):
            lines.append("")
            lines.append("文字圖解：")
            lines.extend(self.bilingualize_known_text(facility.get("diagram_text")).splitlines())
        if facility.get("image_paths"):
            lines.append("")
            lines.append(f"[[IMAGE:{facility.get('image_paths')[0]}]]")
        return "\n".join(lines)

    def resource_summary_text(self, resource_item: dict[str, Any]) -> str:
        head, blueprints = self.resource_summary_parts(resource_item)
        if blueprints:
            return head + "\n\n" + blueprints
        return head
