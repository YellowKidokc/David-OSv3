from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import RuleBrick


def main() -> None:
    parser = argparse.ArgumentParser(description="Rule Brick shared AI work contract")
    parser.add_argument("--state", default=".data/rule-brick")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("questions")
    before = sub.add_parser("before")
    before.add_argument("--agent", required=True)
    before.add_argument("--intent", required=True)
    before.add_argument("--root", action="append", default=[])
    after = sub.add_parser("after")
    after.add_argument("--session", required=True)
    after.add_argument("--status", required=True)
    after.add_argument("--outcome", required=True)
    args = parser.parse_args()
    brick = RuleBrick(Path(args.state))
    try:
        if args.command == "questions":
            result = {"authority": "advisory_only", "questions": brick.questions()}
        elif args.command == "before":
            result = brick.before_work(agent_id=args.agent, intent=args.intent, roots=args.root)
        else:
            result = brick.after_work(session_id=args.session, status=args.status, outcome=args.outcome)
        print(json.dumps(result, indent=2))
    finally:
        brick.close()


if __name__ == "__main__":
    main()
