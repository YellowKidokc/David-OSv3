"""Installable command entry points for local hub operation."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

from hub.services.node_health import NodeHealthService
from hub.storage.db import Database
from hub.storage.job_repo import JobRepo
from hub.storage.memory_repo import MemoryRepo
from hub.storage.node_repo import NodeRepo
from hub.storage.top_of_mind_repo import TopOfMindRepo


def api_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the File Intelligence Hub API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args(argv)
    uvicorn = importlib.import_module("uvicorn")
    uvicorn.run("hub.api.app:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def health_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print local File Intelligence Hub node health")
    parser.add_argument("--db", default=".data/file-intelligence-hub.sqlite3")
    parser.add_argument("--node-id", default="local")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args(argv)
    db = Database(args.db)
    service = NodeHealthService(NodeRepo(db.conn), JobRepo(db.conn), node_id=args.node_id, repo_root=Path(args.repo_root))
    print(json.dumps(service.check_local_health(), sort_keys=True))
    return 0


def top_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Top of Mind command-line client")
    parser.add_argument("--db", default=".data/file-intelligence-hub.sqlite3")
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    post_message = subparsers.add_parser("message-post", help="post a message into Top of Mind")
    post_message.add_argument("--source-id", required=True)
    post_message.add_argument("--source-label")
    post_message.add_argument("--body", required=True)
    post_message.add_argument("--folder", default="Main")
    post_message.add_argument("--wall", default="main")

    memory_add = subparsers.add_parser("memory-add", help="add a memory item")
    memory_add.add_argument("--title", required=True)
    memory_add.add_argument("--body", required=True)
    memory_add.add_argument("--source", default="cli")
    memory_add.add_argument("--folder", default="Memory")
    memory_add.add_argument("--tag", action="append", default=[])
    memory_add.add_argument("--embed", action="store_true")

    memory_search = subparsers.add_parser("memory-search", help="search memory")
    memory_search.add_argument("query")
    memory_search.add_argument("--mode", choices=["text", "vector"], default="text")
    memory_search.add_argument("--limit", type=int, default=10)

    memory_embed = subparsers.add_parser("memory-embed-pending", help="embed memory items without vectors")
    memory_embed.add_argument("--limit", type=int, default=100)

    command_post = subparsers.add_parser("command-post", help="create a command-line job")
    command_post.add_argument("command", nargs="+")
    command_post.add_argument("--cwd")
    command_post.add_argument("--timeout-seconds", type=float, default=60)
    command_post.add_argument("--no-review", action="store_true")

    args = parser.parse_args(argv)
    db = Database(args.db)

    if args.command_name == "message-post":
        result = TopOfMindRepo(db.conn).post_message(
            source_id=args.source_id,
            source_label=args.source_label,
            body=args.body,
            folder=args.folder,
            wall=args.wall,
        )
    elif args.command_name == "memory-add":
        repo = MemoryRepo(db.conn)
        result = repo.create_item(
            title=args.title,
            body=args.body,
            source=args.source,
            folder=args.folder,
            tags=args.tag,
        )
        if args.embed:
            result = repo.update_embedding(int(result["id"]))
    elif args.command_name == "memory-search":
        repo = MemoryRepo(db.conn)
        result = repo.vector_search(args.query, limit=args.limit) if args.mode == "vector" else repo.search(args.query, limit=args.limit)
    elif args.command_name == "memory-embed-pending":
        result = MemoryRepo(db.conn).embed_pending(limit=args.limit)
    elif args.command_name == "command-post":
        payload = {
            "command": args.command,
            "timeout_seconds": args.timeout_seconds,
            "review_required": not args.no_review,
        }
        if args.cwd:
            payload["cwd"] = args.cwd
        repo = JobRepo(db.conn)
        job = repo.create_job("command_line", payload)
        if payload["review_required"]:
            review = repo.create_review_item(job["id"], reason="cli_command_line", action="command_line", payload=payload)
            result = repo.update_job(job["id"], status="waiting_review", result={"review": review, "command": payload})
        else:
            result = job
    else:
        parser.error("unsupported command")
    print(json.dumps(result, sort_keys=True))
    return 0
