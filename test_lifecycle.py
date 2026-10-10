"""The end-to-end lifecycle is the meaningful gate: queue, recovery, review."""
import json
import tempfile
import unittest
from pathlib import Path

from mudo.config import profiles
from mudo.db import connect
from mudo.engine import daily_prepare, first_ready, queue, review, start, step, transcript
from mudo.services import DemoModel
from mudo.local_markov import MarkovBoundary


class Lifecycle(unittest.TestCase):
    def test_nm_baseline_requires_reviewed_examples(self):
        examples = ["작은 팀이 협력해서 제한 시간 안에 낯선 물건을 만든다",
                    "제작진의 새 규칙 때문에 두 팀이 각자의 역할을 바꾼다",
                    "멤버들이 경쟁하다가 결국 서로의 미션을 돕게 된다"]
        self.assertIsNone(MarkovBoundary(examples[:2]).score(examples[0]))
        score = MarkovBoundary(examples).score(examples[0])
        self.assertTrue(0 <= score <= 1)

    def test_two_daily_briefs_resume_episode_and_carry_feedback(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"run.sqlite3"
            model = DemoModel()
            first = daily_prepare("2026-09-29",model,demo=True,path=path)
            same = daily_prepare("2026-09-29",model,demo=True,path=path)
            second = daily_prepare("2026-09-30",model,demo=True,path=path)
            self.assertEqual(first["id"],same["id"])
            self.assertEqual(len(queue(path)),2)
            self.assertEqual(first_ready(path)["id"],first["id"])
            start(first["id"],path)
            for _ in range(17):
                step(first["id"],model,path)
            ep,turns = transcript(first["id"],path)
            self.assertEqual(ep["turn"],17)
            self.assertEqual(len([t for t in turns if t["kind"]=="producer"]),1)
            start(first["id"],path)  # reopening does not erase previous turns
            self.assertEqual(first_ready(path)["id"],first["id"])
            for _ in range(83):
                step(first["id"],model,path)
            ep,turns = transcript(first["id"],path)
            self.assertEqual(ep["status"],"awaiting_review")
            self.assertEqual(len([t for t in turns if t["kind"]=="member"]),100)
            with connect(path) as db:
                before = db.execute("SELECT current FROM relationships WHERE member='yoo' AND other='park'").fetchone()[0]
            ratings = {m["id"]:{"fun":4,"similarity":4,"note":"다음에는 지난 사건 반영"}
                       for m in profiles()}
            review(first["id"],4,4,ratings,"더 짧은 도입",path)
            with connect(path) as db:
                after = db.execute("SELECT current FROM relationships WHERE member='yoo' AND other='park'").fetchone()[0]
                self.assertEqual(db.execute("SELECT COUNT(*) FROM learned_notes").fetchone()[0],8)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM nm_examples").fetchone()[0],1)
            self.assertLessEqual(abs(after),abs(before)+1e-9)
            self.assertEqual(first_ready(path)["id"],second["id"])
            with self.assertRaises(ValueError):
                review(first["id"],4,4,ratings,"중복",path)


if __name__ == "__main__":
    unittest.main()
