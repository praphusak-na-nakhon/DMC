from __future__ import annotations

import json
from dataclasses import dataclass

from .db import connect
from .schemas import ModuleCatalogItem, WalletSnapshot


@dataclass(frozen=True)
class AccountSession:
    token: str
    user_id: str
    email: str
    display_name: str | None
    status: str
    token_expires_at: str
    signed_in_at: str
    last_checked_at: str
    wallet: WalletSnapshot | None
    module_catalog: list[ModuleCatalogItem]


class AccountSessionStore:
    def save_session(
        self,
        *,
        token: str,
        user_id: str,
        email: str,
        display_name: str | None,
        status: str,
        token_expires_at: str,
        checked_at: str,
        wallet: WalletSnapshot | None = None,
        module_catalog: list[ModuleCatalogItem] | None = None,
    ) -> None:
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO account_session (
                    id, token, user_id, email, display_name, status, token_expires_at,
                    signed_in_at, last_checked_at, wallet_json, module_catalog_json
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    token = excluded.token,
                    user_id = excluded.user_id,
                    email = excluded.email,
                    display_name = excluded.display_name,
                    status = excluded.status,
                    token_expires_at = excluded.token_expires_at,
                    last_checked_at = excluded.last_checked_at,
                    wallet_json = excluded.wallet_json,
                    module_catalog_json = excluded.module_catalog_json
                """,
                (
                    token,
                    user_id,
                    email,
                    display_name,
                    status,
                    token_expires_at,
                    checked_at,
                    checked_at,
                    wallet.model_dump_json() if wallet is not None else "{}",
                    json.dumps(
                        [item.model_dump(mode="python") for item in module_catalog or []],
                        ensure_ascii=False,
                    ),
                ),
            )

    def update_wallet(self, wallet: WalletSnapshot, *, checked_at: str) -> None:
        with connect() as connection:
            connection.execute(
                """
                UPDATE account_session
                SET wallet_json = ?, last_checked_at = ?
                WHERE id = 1
                """,
                (wallet.model_dump_json(), checked_at),
            )

    def update_module_catalog(self, modules: list[ModuleCatalogItem], *, checked_at: str) -> None:
        with connect() as connection:
            connection.execute(
                """
                UPDATE account_session
                SET module_catalog_json = ?, last_checked_at = ?
                WHERE id = 1
                """,
                (
                    json.dumps([item.model_dump(mode="python") for item in modules], ensure_ascii=False),
                    checked_at,
                ),
            )

    def get_session(self) -> AccountSession | None:
        with connect() as connection:
            row = connection.execute("SELECT * FROM account_session WHERE id = 1").fetchone()
        if row is None:
            return None

        wallet_payload = json.loads(row["wallet_json"] or "{}")
        wallet = WalletSnapshot.model_validate(wallet_payload) if wallet_payload else None
        module_payload = json.loads(row["module_catalog_json"] or "[]")
        modules = [ModuleCatalogItem.model_validate(item) for item in module_payload]
        return AccountSession(
            token=row["token"],
            user_id=row["user_id"],
            email=row["email"],
            display_name=row["display_name"],
            status=row["status"],
            token_expires_at=row["token_expires_at"],
            signed_in_at=row["signed_in_at"],
            last_checked_at=row["last_checked_at"],
            wallet=wallet,
            module_catalog=modules,
        )

    def clear(self) -> None:
        with connect() as connection:
            connection.execute("DELETE FROM account_session WHERE id = 1")
