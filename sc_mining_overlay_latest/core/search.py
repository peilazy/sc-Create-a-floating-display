from __future__ import annotations

from difflib import SequenceMatcher

from core.data_store import MiningDataStore


class MiningSearch:
    def __init__(self, store: MiningDataStore) -> None:
        self.store = store
        self.index = self._build_index()
        self.resource_catalog = self._build_resource_catalog()

    def _build_index(self) -> list[dict]:
        rows = []
        for body in self.store.all_bodies():
            bag = [
                body["name_en"], body["name_zh"], body["system"], body["system_zh"],
                body.get("parent") or "", body["type"], self._type_to_zh(body["type"])
            ]
            mining = body.get("mining", {})
            resource_terms = set()
            for item in body.get("locations", []):
                bag.append(item)
                bag.append(self.store.translate_known_text(item))
            for group in (
                mining.get("known_surface_resources", []),
                mining.get("known_cave_resources", []),
                mining.get("known_asteroid_resources", []),
            ):
                for item in group:
                    terms = self.store.extract_resource_terms(item)
                    for term in terms:
                        resource_terms.add(term)
                        translated = self.store.translate_resource_name(term)
                        if translated:
                            resource_terms.add(translated)
                    bag.extend(list(resource_terms))
            blob = " ".join(filter(None, bag)).lower()
            rows.append({
                "id": body["id"],
                "name_en": body["name_en"],
                "name_zh": body["name_zh"],
                "system": body["system"],
                "system_zh": body["system_zh"],
                "type": body["type"],
                "blob": blob,
                "resource_terms": sorted(resource_terms),
            })
        return rows

    def _build_resource_catalog(self) -> list[dict]:
        catalog: dict[str, dict] = {}
        for row in self.index:
            for term in row.get("resource_terms", []):
                term = (term or "").strip()
                if not term:
                    continue
                key = term.lower()
                entry = catalog.setdefault(key, {
                    "key": key,
                    "display": term,
                    "bodies": [],
                    "body_ids": set(),
                    "aliases": set(),
                })
                translated = self.store.translate_resource_name(term)
                if translated:
                    entry["aliases"].add(translated.lower())
                entry["aliases"].add(term.lower())
                if row["id"] not in entry["body_ids"]:
                    entry["body_ids"].add(row["id"])
                    entry["bodies"].append({
                        "id": row["id"],
                        "name_zh": row["name_zh"],
                        "name_en": row["name_en"],
                        "system_zh": row["system_zh"],
                        "system": row["system"],
                    })
        out = []
        for entry in catalog.values():
            entry["aliases"] = sorted(entry["aliases"])
            entry.pop("body_ids", None)
            out.append(entry)
        out.sort(key=lambda x: (len(x["display"]), x["display"].lower()))
        return out

    def suggest(self, query: str, recent: list[str] | None = None, limit: int = 10) -> list[dict]:
        q = (query or "").strip().lower()
        suggestions: list[tuple[float, dict]] = []

        if not q:
            recent = recent or []
            seen = set()
            out = []
            for item in recent:
                key = item.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                out.append({"kind": "recent", "display": item, "query": item})
                if len(out) >= limit:
                    break
            return out

        for item in self.resource_catalog:
            score = self._resource_suggest_score(q, item)
            if score > 0:
                label = item["display"]
                translated = self.store.translate_resource_name(label)
                if translated:
                    label = translated
                meta = f'{len(item["bodies"])} 個地點'
                suggestions.append((score + 0.25, {"kind": "resource", "display": label, "query": label, "meta": meta}))

        for row in self.index:
            label = row["name_zh"] or row["name_en"]
            for cand in [row["name_zh"], row["name_en"], row["system_zh"], row["system"]]:
                if not cand:
                    continue
                score = self._body_suggest_score(q, cand.lower())
                if score > 0:
                    suggestions.append((score, {
                        "kind": "body",
                        "display": label,
                        "query": row["name_zh"] or row["name_en"],
                        "meta": row["system_zh"] or row["system"],
                        "body_id": row["id"],
                    }))
                    break

        suggestions.sort(key=lambda x: x[0], reverse=True)
        out = []
        seen = set()
        for _, item in suggestions:
            key = (item["kind"], item["display"], item.get("meta", ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
            if len(out) >= limit:
                break
        return out

    def search(self, query: str, limit: int = 24) -> list[dict]:
        q = (query or "").strip().lower()
        if not q:
            return sorted(
                self.index,
                key=lambda row: (
                    0 if row["type"] in {"planet", "moon", "asteroid_belt", "asteroid_cluster", "ring", "asteroid_world"} else 1,
                    (row["name_zh"] or row["name_en"]).lower(),
                ),
            )[:limit]
        scored = []
        for row in self.index:
            score = self._score(q, row)
            if score >= 0.16:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [row for _, row in scored[:limit]]

    def resource_related_bodies(self, resource_query: str, limit: int = 24) -> list[dict]:
        q = (resource_query or "").strip().lower()
        if not q:
            return []
        scored = []
        for row in self.index:
            score = 0.0
            for term in row.get("resource_terms", []):
                t = term.lower()
                if q == t:
                    score = max(score, 1.0)
                elif t.startswith(q):
                    score = max(score, 0.95)
                elif q in t and len(q) >= 2:
                    score = max(score, 0.90)
                else:
                    ratio = SequenceMatcher(None, q, t).ratio()
                    if len(q) >= 2 and ratio >= 0.72:
                        score = max(score, ratio * 0.85)
            if score >= 0.35:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [row for _, row in scored[:limit]]

    @staticmethod
    def _type_to_zh(kind: str) -> str:
        return {
            "planet": "行星",
            "moon": "衛星",
            "asteroid_belt": "小行星帶",
            "asteroid_cluster": "小行星群",
            "ring": "環帶",
            "asteroid_world": "小行星世界",
        }.get(kind, kind)

    @staticmethod
    def _resource_suggest_score(q: str, item: dict) -> float:
        best = 0.0
        for cand in item.get("aliases", []):
            if q == cand:
                best = max(best, 1.0)
            elif cand.startswith(q):
                best = max(best, 0.97)
            elif len(q) >= 2 and q in cand:
                best = max(best, 0.90)
            else:
                ratio = SequenceMatcher(None, q, cand).ratio()
                # stricter for non-prefix chinese/short queries to avoid nonsense matches
                threshold = 0.86 if len(q) <= 3 else 0.74
                if ratio >= threshold:
                    best = max(best, ratio * 0.82)
        return best

    @staticmethod
    def _body_suggest_score(q: str, cand: str) -> float:
        if not q or not cand:
            return 0.0
        if q == cand:
            return 1.0
        if cand.startswith(q):
            return 0.95
        if len(q) >= 2 and q in cand:
            return 0.84
        ratio = SequenceMatcher(None, q, cand).ratio()
        threshold = 0.88 if len(q) <= 2 else 0.76
        return ratio * 0.72 if ratio >= threshold else 0.0

    @staticmethod
    def _score(q: str, row: dict) -> float:
        blob = row["blob"]
        name = f'{row["name_en"]} {row["name_zh"]} {row["system"]} {row["system_zh"]}'.lower()
        exacts = {row["name_en"].lower(), row["name_zh"].lower(), row["system"].lower(), row["system_zh"].lower()}
        if q in exacts:
            return 1.0
        if q in name:
            return 0.95
        if len(q) >= 2 and q in blob:
            return 0.82
        best = max(
            SequenceMatcher(None, q, name).ratio() * 0.82,
            SequenceMatcher(None, q, blob[: max(220, len(q) * 26)]).ratio() * 0.72,
        )
        return best
