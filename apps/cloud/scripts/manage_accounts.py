from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.account_service import AccountRepository
from app.config import settings
from app.db import migrate_database
from app.schemas import CloudCreditTopupRequest, CloudUserCreateRequest, CloudUserUpdateRequest
from app.schemas import CloudCreditTopupDecisionRequest, CloudCreditTopupRequestCreate


def _print_json(value: Any) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _repo() -> AccountRepository:
    migrate_database(Path(settings.sqlite_path))
    return AccountRepository()


def _resolve_user_id(repo: AccountRepository, *, user_id: str | None, email: str | None) -> str:
    if user_id:
        return user_id
    if not email:
        raise SystemExit("Specify --user-id or --email.")
    user = repo.get_user_by_email(email)
    if user is None:
        raise SystemExit(f"User not found for email: {email}")
    return user.user_id


def create_user(args: argparse.Namespace) -> None:
    repo = _repo()
    user = repo.create_user(
        CloudUserCreateRequest(
            email=args.email,
            password=args.password,
            display_name=args.display_name,
            status=args.status,
        )
    )
    _print_json(user)


def seed_user(args: argparse.Namespace) -> None:
    repo = _repo()
    existing = repo.get_user_by_email(args.email)
    if existing is None:
        user = repo.create_user(
            CloudUserCreateRequest(
                email=args.email,
                password=args.password,
                display_name=args.display_name,
                status=args.status,
            )
        )
        _print_json({"action": "created", "user": user.model_dump()})
        return

    user = repo.update_user(
        existing.user_id,
        CloudUserUpdateRequest(
            password=args.password if args.reset_password else None,
            display_name=args.display_name,
            status=args.status,
        ),
    )
    _print_json({"action": "updated", "user": user.model_dump()})


def show_user(args: argparse.Namespace) -> None:
    repo = _repo()
    user_id = _resolve_user_id(repo, user_id=args.user_id, email=args.email)
    user = repo.get_user_admin(user_id)
    if user is None:
        raise SystemExit(f"User not found: {user_id}")
    _print_json(user)


def update_user(args: argparse.Namespace) -> None:
    repo = _repo()
    user_id = _resolve_user_id(repo, user_id=args.user_id, email=args.email)
    user = repo.update_user(
        user_id,
        CloudUserUpdateRequest(
            password=args.password,
            display_name=args.display_name,
            status=args.status,
        ),
    )
    _print_json(user)


def topup_user(args: argparse.Namespace) -> None:
    repo = _repo()
    user_id = _resolve_user_id(repo, user_id=args.user_id, email=args.email)
    wallet = repo.topup_user(
        user_id,
        CloudCreditTopupRequest(
            amount=args.amount,
            note=args.note,
            idempotency_key=args.idempotency_key,
        ),
    )
    _print_json(wallet)


def request_topup(args: argparse.Namespace) -> None:
    repo = _repo()
    user_id = _resolve_user_id(repo, user_id=args.user_id, email=args.email)
    topup_request = repo.create_topup_request(
        user_id,
        CloudCreditTopupRequestCreate(
            amount=args.amount,
            note=args.note,
            payment_reference=args.payment_reference,
        ),
        actor=args.actor,
    )
    _print_json(topup_request)


def decide_topup(args: argparse.Namespace) -> None:
    repo = _repo()
    response = repo.decide_topup_request(
        args.request_id,
        CloudCreditTopupDecisionRequest(
            decision=args.decision,
            note=args.note,
            idempotency_key=args.idempotency_key,
        ),
        actor=args.actor,
    )
    _print_json(response)


def show_ledger(args: argparse.Namespace) -> None:
    repo = _repo()
    user_id = _resolve_user_id(repo, user_id=args.user_id, email=args.email)
    entries = repo.list_ledger(user_id)[: args.limit]
    _print_json([entry.model_dump() for entry in entries])


def list_users(args: argparse.Namespace) -> None:
    repo = _repo()
    users = repo.list_users(limit=args.limit, offset=args.offset)
    _print_json([user.model_dump() for user in users])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage staging cloud users and credit wallets.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-user", help="Create an admin-provisioned user.")
    create.add_argument("--email", required=True)
    create.add_argument("--password", required=True)
    create.add_argument("--display-name")
    create.add_argument("--status", choices=["active", "disabled"], default="active")
    create.set_defaults(func=create_user)

    seed = subparsers.add_parser("seed-user", help="Create or update a staging user idempotently.")
    seed.add_argument("--email", required=True)
    seed.add_argument("--password", required=True)
    seed.add_argument("--display-name")
    seed.add_argument("--status", choices=["active", "disabled"], default="active")
    seed.add_argument(
        "--reset-password",
        action="store_true",
        help="Reset password when the user already exists. By default existing passwords are left unchanged.",
    )
    seed.set_defaults(func=seed_user)

    show = subparsers.add_parser("show", help="Show a user and wallet.")
    show.add_argument("--email")
    show.add_argument("--user-id")
    show.set_defaults(func=show_user)

    update = subparsers.add_parser("update-user", help="Update display name, password, or status.")
    update.add_argument("--email")
    update.add_argument("--user-id")
    update.add_argument("--password")
    update.add_argument("--display-name")
    update.add_argument("--status", choices=["active", "disabled"])
    update.set_defaults(func=update_user)

    topup = subparsers.add_parser("topup", help="Manually add credits after payment verification.")
    topup.add_argument("--email")
    topup.add_argument("--user-id")
    topup.add_argument("--amount", type=int, required=True)
    topup.add_argument("--note")
    topup.add_argument("--idempotency-key")
    topup.set_defaults(func=topup_user)

    request_topup_command = subparsers.add_parser("request-topup", help="Create a pending top-up approval request.")
    request_topup_command.add_argument("--email")
    request_topup_command.add_argument("--user-id")
    request_topup_command.add_argument("--amount", type=int, required=True)
    request_topup_command.add_argument("--note")
    request_topup_command.add_argument("--payment-reference")
    request_topup_command.add_argument("--actor", default="cli-admin")
    request_topup_command.set_defaults(func=request_topup)

    decide_topup_command = subparsers.add_parser("decide-topup", help="Approve or reject a pending top-up request.")
    decide_topup_command.add_argument("--request-id", required=True)
    decide_topup_command.add_argument("--decision", choices=["approved", "rejected"], required=True)
    decide_topup_command.add_argument("--note")
    decide_topup_command.add_argument("--idempotency-key")
    decide_topup_command.add_argument("--actor", default="cli-admin")
    decide_topup_command.set_defaults(func=decide_topup)

    ledger = subparsers.add_parser("ledger", help="Show recent credit ledger entries.")
    ledger.add_argument("--email")
    ledger.add_argument("--user-id")
    ledger.add_argument("--limit", type=int, default=20)
    ledger.set_defaults(func=show_ledger)

    list_command = subparsers.add_parser("list-users", help="List users and wallets.")
    list_command.add_argument("--limit", type=int, default=100)
    list_command.add_argument("--offset", type=int, default=0)
    list_command.set_defaults(func=list_users)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
