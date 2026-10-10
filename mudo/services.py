"""Model and search adapters. The durable decisions live in the application."""
import hashlib
import importlib
import json
import os

from .molang_nm_guard import source_trust


def query_for(member, day):
    choices = member["searches"]
    n = int(hashlib.sha256((day + member["id"]).encode()).hexdigest()[:8], 16)
    return choices[n % len(choices)]


def search(query, demo=False):
    if demo:
        return [{"title": f"실험용 소재: {query}", "snippet":
                 f"{query}를 바탕으로 한 가상의 팀 미션. 참가자들이 서로 다른 선택을 할 수 있다.",
                 "url": "https://example.com/demo/" + hashlib.sha256(query.encode()).hexdigest()[:12]}]
    key = os.environ.get("BRAVE_API_KEY")
    if not key:
        raise RuntimeError("BRAVE_API_KEY가 없습니다. 실제 소재 수집에는 Brave 키가 필요합니다. (--demo는 모의 자료)")
    from .molang_search import brave_search
    return brave_search(key, query, count=3)


def nm_score(text, examples=()):
    """A real trained NM must expose score(text)->0..1; absence is explicit."""
    module = os.environ.get("MUDO_NM_MODULE", "").strip()
    if not module:
        from .local_markov import MarkovBoundary
        estimate = MarkovBoundary(examples).score(text)
        return (estimate, "local_markov") if estimate is not None else (None, "untrained")
    engine = importlib.import_module(module)
    result = float(engine.score(text))
    if not 0 <= result <= 1:
        raise ValueError("NM 플러그인의 score(text)는 0..1을 반환해야 합니다")
    return result, "trained"


def candidates(member, day, items, examples=()):
    records = []
    for hit in items:
        title, snippet, url = [str(hit.get(k) or "").strip() for k in ("title", "snippet", "url")]
        if not title or not url:
            continue
        trust = source_trust(url)  # adapted from Molang's NM-style boundary guard
        if trust < .12:
            continue
        nm, mode = nm_score(title + " " + snippet, examples)
        affinity = max((1 if word in (title + snippet) else 0)
                       for word in member["searches"][0].split()) if member["searches"] else 0
        rank = round(.75 * trust + .10 * affinity + (.15 * nm if nm is not None else 0), 4)
        records.append({"day": day, "member": member["id"], "query": query_for(member, day),
                        "topic": title[:80], "title": title[:200], "snippet": snippet[:700],
                        "url": url[:500], "source_score": trust, "nm_score": nm,
                        "nm_mode": mode, "rank_score": rank})
    return records


class Model:
    def __init__(self):
        from openai import OpenAI
        key = os.environ.get("OPENAI_API_KEY", "")
        base = os.environ.get("OPENAI_BASE_URL", "")
        if not key and not base:
            raise RuntimeError("OPENAI_API_KEY 또는 OPENAI_BASE_URL을 설정하세요 (--demo는 모의 모델)")
        self.client = OpenAI(api_key=key or "local", base_url=base or None)
        self.model = os.environ.get("MUDO_MODEL", "gpt-4o-mini")

    def generate(self, kind, system, payload):
        messages = [{"role":"system","content":system},
                    {"role":"user","content":json.dumps(payload,ensure_ascii=False)}]
        try:
            response = self.client.chat.completions.create(model=self.model,
                messages=messages, response_format={"type":"json_object"}, temperature=.75)
        except Exception as exc:
            # Some OpenAI-compatible local servers reject response_format.
            if not any(word in str(exc).lower() for word in ("response_format","json_object")):
                raise
            response = self.client.chat.completions.create(model=self.model,
                messages=messages, temperature=.75)
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n",1)[-1].rsplit("```",1)[0].strip()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("모델 응답이 JSON 객체가 아닙니다")
        return data


class DemoModel:
    """Deterministic mechanics demonstration; never presented as independent AI."""
    def generate(self, kind, system, payload):
        if kind == "plan":
            pick = payload["candidates"][0]
            return {"title": "일곱 사람의 낯선 미션", "premise": pick["title"],
                    "selected_url": pick["url"],
                    "start": "소재를 보고 세 팀으로 나뉘어 작은 도전을 시작한다.",
                    "mid_events": ["준비한 소품 하나가 사라진다", "서로의 역할을 교환한다"],
                    "finish": "마지막 선택이 준비한 계획을 어떻게 바꾸었는지 보여준다",
                    "why": "선택과 갈등이 생길 수 있는 소재"}
        if kind == "producer":
            return {"event": "제작진이 서로의 역할을 바꾸라는 봉투를 건넨다."}
        if kind == "recap":
            return {"recap": payload["previous_recap"] + " " +
                    " / ".join(x["speaker"] + ":" + x["action"] for x in payload["new_turns"])}
        member = payload["member"]
        n = payload["next_turn"]
        target = payload["others"][n % len(payload["others"])] if payload["others"] else ""
        return {"action": f"{member['name']}이(가) {target or '소품'}에게 새로운 임무를 제안한다",
                "line": f"이번에는 {target or '우리'}가 다른 방법으로 해보자.",
                "target": target, "relation_delta": .08 if n % 3 else -.12,
                "memory": f"{target}와의 역할 교환을 떠올린다"}
