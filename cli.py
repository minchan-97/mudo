"""Usage: python -m mudo.cli --help"""
import argparse
import json

from .config import profiles
from .engine import (MAX_TURNS, daily_prepare, first_ready, queue, review,
                     start, step, today, transcript)
from .services import DemoModel, Model


def main():
    ap = argparse.ArgumentParser(description="개인용 가상 예능 기획·재생")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("daily", help="하루 한 번 검색하고 기획안을 대기열에 추가")
    p.add_argument("--day", default=today(), help="Asia/Seoul 날짜 YYYY-MM-DD")
    p.add_argument("--demo", action="store_true", help="네트워크 없는 기계적 예시")
    sub.add_parser("queue", help="쌓인 에피소드 목록")
    p = sub.add_parser("play", help="오래된 대기 편부터 진행하고 매 턴 저장")
    p.add_argument("--limit", type=int, default=10, help="이번 실행에서 진행할 턴 수 (최대 100)")
    p.add_argument("--demo", action="store_true", help="네트워크 없는 기계적 예시")
    p = sub.add_parser("show", help="지난 턴 읽기")
    p.add_argument("episode_id",type=int)
    p = sub.add_parser("review", help="100턴이 끝난 회차 평가")
    p.add_argument("episode_id",type=int)
    p.add_argument("json_file",help="평가 JSON 파일 경로")
    args = ap.parse_args()
    if args.command == "daily":
        ep = daily_prepare(args.day,DemoModel() if args.demo else Model(),demo=args.demo)
        print(f"{ep['day']} · 편 #{ep['id']} · {json.loads(ep['plan'])['title']}")
    elif args.command == "queue":
        for r in queue():
            print(f"{r['id']:>3} | {r['day']} | {r['status']:<15} | {r['turn']:>3}/{MAX_TURNS} | "
                  f"{json.loads(r['plan'])['title']}")
    elif args.command == "show":
        ep, turns = transcript(args.episode_id)
        print(ep["day"],json.loads(ep["plan"])["title"],ep["status"])
        for r in turns:
            print(f"{r['number']:>3} {r['speaker']}: {r['action']} {r['line']}")
    elif args.command == "play":
        if not 1 <= args.limit <= MAX_TURNS:
            ap.error("--limit은 1~100 사이여야 합니다")
        episode = first_ready()
        if not episode:
            ap.error("대기열이 비었습니다. daily를 먼저 실행하세요")
        eid = start(episode["id"])
        model = DemoModel() if args.demo else Model()
        for _ in range(min(args.limit,MAX_TURNS-episode["turn"])):
            t = step(eid,model)
            print(f"{t['number']:>3} {t['speaker']}: {t['line']} ({t['action']})",flush=True)
        ep,_ = transcript(eid)
        print(f"회차 #{eid}: {ep['turn']}/{MAX_TURNS}, 상태 {ep['status']}")
    elif args.command == "review":
        with open(args.json_file,encoding="utf-8") as f:
            data = json.load(f)
        review(args.episode_id,data["pd_fun"],data["pd_similarity"],
               data["members"],data.get("pd_note", ""))
        print("평가 반영 완료. 다음 대기 편부터 이어집니다.")


if __name__ == "__main__":
    main()

