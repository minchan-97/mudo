"""organism/nm_guard.py — NM-style boundary guard (수정판).

원본 대비 바뀐 점:
  1. 도메인 매칭 버그: ('.'+suf) in host 는 부분 문자열 매칭이라
     'my.education.com' 이 'edu' 에 걸렸다. 라벨 경계로 고침.
  2. 한국 도메인 누락: SEEDS 가 전부 한국어인데 화이트리스트에
     ac.kr / go.kr 뿐이라 kasi.re.kr(한국천문연구원)이 네이버 블로그와
     같은 0.42 였다. re.kr / or.kr / 주요 언론·기관 추가.
  3. quality 가 죽은 항이었다: len(text)/700 인데 Brave description 은
     150~200자라 항상 0.25 근처 상수. 240 기준으로 재보정.
  4. evaluate() 가 novelty / prev_topic 을 인자로 받는다. 배치 내에서
     같은 스냅샷을 쓰기 위함 (worker 쪽 순서 의존 버그 수정).

탐색은 막지 않는다. 이 게이트는 장기기억 편입 전 면역계다.
"""
from __future__ import annotations
from urllib.parse import urlparse

TRUST = {
    # 국제 학술·공공
    "nature.com": .92, "science.org": .92, "nih.gov": .95, "nasa.gov": .95,
    "noaa.gov": .93, "arxiv.org": .80, "doi.org": .85, "who.int": .90,
    "oecd.org": .85, "britannica.com": .78, "wikipedia.org": .72,
    "openai.com": .85,
    # 일반 접미사
    "gov": .90, "edu": .82,
    # 한국 기관 — 원본에 누락돼 있던 부분
    "go.kr": .90,     # 정부
    "re.kr": .85,     # 정부출연연구기관 (KASI, KIST, KRISS ...)
    "ac.kr": .85,     # 대학
    "or.kr": .62,     # 협회·비영리. 편차가 커서 낮게.
    # 한국 언론 — 화이트리스트가 아니라 quarantine 경계선 용도
    "yna.co.kr": .70,   # 연합뉴스
    "ebs.co.kr": .70,
    "kbs.co.kr": .64,
    # 국제 언론
    "reuters.com": .75, "apnews.com": .75, "bbc.com": .74, "bbc.co.uk": .74,
}

BLOCK = ("pinterest.", "facebook.", "instagram.", "tiktok.", "x.com",
         "threads.net")

# Brave description 실측 길이 기준. 700자는 도달 불가능한 값이었다.
QUALITY_FULL_AT = 240
MIN_TEXT_LEN = 80
CANDIDATE_SCORE = .62
CANDIDATE_TRUST = .55


def _host(url: str) -> str:
    try:
        h = urlparse(url).netloc.lower().split(':')[0]
        return h[4:] if h.startswith('www.') else h
    except Exception:
        return ''


def _matches(host: str, suffix: str) -> bool:
    """라벨 경계 매칭. 'edu' 가 'education.com' 에 걸리지 않게."""
    return host == suffix or host.endswith('.' + suffix)


def source_trust(url: str) -> float:
    host = _host(url)
    if not host:
        return .25
    if any(b in host for b in BLOCK):
        return .05
    best = .42
    for suf, w in TRUST.items():
        if _matches(host, suf):
            best = max(best, w)
    return best


def transition_prob(state, prev, cur) -> float:
    if not prev or not cur or prev == cur:
        return .5
    pref = prev + ' -> '
    total = sum(v for k, v in state.transition_counts.items()
                if k.startswith(pref))
    hit = state.transition_counts.get(f"{prev} -> {cur}", 0)
    # Laplace 스무딩. 의도적으로 0 이 되지 않게 해 novelty 를 살린다.
    return (hit + 1) / (total + max(8, len(state.interests) or 8))


def evaluate(state, item, novelty=None, prev_topic=None):
    """
    novelty / prev_topic 을 넘기면 그 값을 쓴다.
    넘기지 않으면 예전처럼 state 에서 즉석 계산한다 (하위 호환).

    배치 처리에서는 반드시 사이클 시작 시점 스냅샷을 넘길 것.
    안 그러면 같은 내용이 결과 순서에 따라 다른 판정을 받는다.
    """
    text = (item.get('title', '') + ' ' + item.get('text', '')).strip()
    topic = item.get('topic', '')

    trust = source_trust(item.get('url', ''))
    quality = min(1.0, len(text) / QUALITY_FULL_AT)
    nov = state.novelty(topic) if novelty is None else novelty
    prev = state.last_topic if prev_topic is None else prev_topic
    tp = transition_prob(state, prev, topic)

    score = .45 * trust + .20 * quality + .15 * min(1, tp * 4) + .20 * nov

    if len(text) < MIN_TEXT_LEN or trust < .12:
        status = 'reject'
    elif score >= CANDIDATE_SCORE and trust >= CANDIDATE_TRUST:
        status = 'candidate'
    else:
        status = 'quarantine'

    return {
        "status": status,
        "score": round(score, 3),
        "source_trust": round(trust, 3),
        "transition_p": round(tp, 4),
        "novelty": round(nov, 3),
    }
