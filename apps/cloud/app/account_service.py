from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from fastapi import HTTPException, status

from .config import settings
from .db import connect, utc_now
from .schemas import (
    AccountResponse,
    AccountStatus as CloudAccountStatus,
    AdminAuditEntry,
    CloudCreditTopupDecisionRequest,
    CloudCreditTopupRequest,
    CloudCreditTopupRequestCreate,
    CloudCreditTopupRequestResponse,
    CreditTopupRequestStatus,
    CloudUserAdminResponse,
    CloudUserCreateRequest,
    CloudUserUpdateRequest,
    CreditCaptureRequest,
    CreditLedgerEntry,
    CreditReleaseRequest,
    CreditReservationStatus,
    CreditReservationRequest,
    CreditReservationResponse,
    ModuleCatalogItem,
    ModuleCatalogResponse,
    WalletResponse,
)


MODULE_CATALOG = (
    ModuleCatalogItem(
        id="formConverter",
        enabled=True,
        requires_credits=True,
        pricing_mode="per_billable_record",
        credit_per_unit=1,
        production_dry_run_enabled=False,
    ),
    ModuleCatalogItem(
        id="currentStudents",
        enabled=True,
        requires_credits=True,
        pricing_mode="per_billable_record",
        credit_per_unit=1,
        production_dry_run_enabled=False,
    ),
    ModuleCatalogItem(
        id="graduation",
        enabled=True,
        requires_credits=True,
        pricing_mode="per_billable_record",
        credit_per_unit=1,
        production_dry_run_enabled=False,
    ),
)


@dataclass(frozen=True)
class SessionRecord:
    token: str
    user_id: str
    email: str
    display_name: str | None
    status: str
    expires_at: str


def _now_dt() -> datetime:
    return datetime.now(UTC)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _to_utc_string(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid email")
    return normalized


def _hash_password(password: str, *, salt: bytes | None = None) -> str:
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = encoded.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    expected = _hash_password(password, salt=bytes.fromhex(salt_hex))
    return hmac.compare_digest(expected, f"{algorithm}${salt_hex}${digest_hex}")


class AccountRepository:
    def __init__(self, sqlite_path: str | None = None) -> None:
        self.sqlite_path = Path(sqlite_path or settings.sqlite_path)

    def create_user(self, request: CloudUserCreateRequest) -> CloudUserAdminResponse:
        email = _normalize_email(request.email)
        user_id = str(uuid.uuid4())
        now = utc_now()
        try:
            with connect(self.sqlite_path) as connection:
                connection.execute(
                    """
                    INSERT INTO users (
                        id, email, password_hash, display_name, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        email,
                        _hash_password(request.password),
                        request.display_name,
                        request.status,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO wallets (user_id, balance, updated_at)
                    VALUES (?, 0, ?)
                    """,
                    (user_id, now),
                )
        except Exception as exc:
            if "UNIQUE" in str(exc).upper():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already exists") from exc
            raise

        user = self.get_user_admin(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="user was not created")
        return user

    def authenticate(
        self,
        *,
        email: str,
        password: str,
        device_id: str,
        device_name: str,
        app_version: str,
    ) -> tuple[str, AccountResponse]:
        normalized_email = _normalize_email(email)
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (normalized_email,),
            ).fetchone()
        if row is None or not _verify_password(password, str(row["password_hash"])):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
        if row["status"] != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account is disabled")

        token = secrets.token_urlsafe(32)
        now_dt = _now_dt()
        expires_at = _to_utc_string(now_dt + timedelta(hours=settings.session_duration_hours))
        with connect(self.sqlite_path) as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    token, user_id, device_id, device_name, app_version, created_at, expires_at, revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    token,
                    str(row["id"]),
                    device_id,
                    device_name,
                    app_version,
                    _to_utc_string(now_dt),
                    expires_at,
                ),
            )

        return token, AccountResponse(
            user_id=str(row["id"]),
            email=str(row["email"]),
            display_name=row["display_name"],
            status=cast(CloudAccountStatus, row["status"]),
            token_expires_at=expires_at,
        )

    def get_session(self, token: str) -> SessionRecord:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                """
                SELECT sessions.token, sessions.user_id, sessions.expires_at,
                       users.email, users.display_name, users.status
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ? AND sessions.revoked_at IS NULL
                """,
                (token,),
            ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
        if _parse_utc(str(row["expires_at"])) <= _now_dt():
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="session expired")
        if row["status"] != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="account is disabled")
        return SessionRecord(
            token=str(row["token"]),
            user_id=str(row["user_id"]),
            email=str(row["email"]),
            display_name=row["display_name"],
            status=str(row["status"]),
            expires_at=str(row["expires_at"]),
        )

    def revoke_session(self, token: str) -> None:
        with connect(self.sqlite_path) as connection:
            connection.execute(
                "UPDATE sessions SET revoked_at = ? WHERE token = ?",
                (utc_now(), token),
            )

    def account_response(self, session: SessionRecord) -> AccountResponse:
        return AccountResponse(
            user_id=session.user_id,
            email=session.email,
            display_name=session.display_name,
            status="active",
            token_expires_at=session.expires_at,
        )

    def get_wallet(self, user_id: str) -> WalletResponse:
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                "SELECT balance FROM wallets WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            reserved_row = connection.execute(
                """
                SELECT COALESCE(SUM(units_reserved - units_captured - units_released), 0) AS reserved
                FROM credit_reservations
                WHERE user_id = ? AND status = 'active'
                """,
                (user_id,),
            ).fetchone()
        balance = int(row["balance"]) if row is not None else 0
        reserved = int(reserved_row["reserved"]) if reserved_row is not None else 0
        return WalletResponse(
            user_id=user_id,
            balance=balance,
            reserved=reserved,
            available=max(balance - reserved, 0),
        )

    def topup_user(self, user_id: str, request: CloudCreditTopupRequest) -> WalletResponse:
        idempotency_key = request.idempotency_key or f"admin-topup-{uuid.uuid4()}"
        with connect(self.sqlite_path) as connection:
            existing = connection.execute(
                """
                SELECT 1 FROM credit_transactions
                WHERE user_id = ? AND idempotency_key = ?
                """,
                (user_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                return self.get_wallet(user_id)

            if connection.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

            now = utc_now()
            connection.execute(
                "UPDATE wallets SET balance = balance + ?, updated_at = ? WHERE user_id = ?",
                (request.amount, now, user_id),
            )
            connection.execute(
                """
                INSERT INTO credit_transactions (
                    id, user_id, type, amount, reservation_id, job_id, module,
                    idempotency_key, note, created_at
                )
                VALUES (?, ?, 'topup', ?, NULL, NULL, NULL, ?, ?, ?)
                """,
                (str(uuid.uuid4()), user_id, request.amount, idempotency_key, request.note, now),
            )
        return self.get_wallet(user_id)

    def record_admin_audit(
        self,
        *,
        actor: str,
        action: str,
        target_type: str | None,
        target_id: str | None,
        payload: dict[str, object] | None = None,
    ) -> None:
        with connect(self.sqlite_path) as connection:
            self._record_admin_audit(
                connection,
                actor=actor,
                action=action,
                target_type=target_type,
                target_id=target_id,
                payload=payload or {},
            )

    def list_admin_audit(self, *, limit: int = 100, offset: int = 0) -> list[AdminAuditEntry]:
        safe_limit = min(max(limit, 1), 500)
        safe_offset = max(offset, 0)
        with connect(self.sqlite_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM admin_audit_log
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (safe_limit, safe_offset),
            ).fetchall()
        return [
            AdminAuditEntry(
                audit_id=str(row["id"]),
                actor=str(row["actor"]),
                action=str(row["action"]),
                target_type=row["target_type"],
                target_id=row["target_id"],
                payload=cast(dict[str, object], json.loads(str(row["payload_json"]))),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def create_topup_request(
        self,
        user_id: str,
        request: CloudCreditTopupRequestCreate,
        *,
        actor: str,
    ) -> CloudCreditTopupRequestResponse:
        with connect(self.sqlite_path) as connection:
            if connection.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
            request_id = str(uuid.uuid4())
            now = utc_now()
            connection.execute(
                """
                INSERT INTO credit_topup_requests (
                    id, user_id, amount, status, note, payment_reference, requested_by,
                    decided_by, topup_idempotency_key, created_at, updated_at, decided_at
                )
                VALUES (?, ?, ?, 'pending', ?, ?, ?, NULL, NULL, ?, ?, NULL)
                """,
                (
                    request_id,
                    user_id,
                    request.amount,
                    request.note,
                    request.payment_reference,
                    actor,
                    now,
                    now,
                ),
            )
            self._record_admin_audit(
                connection,
                actor=actor,
                action="credit_topup_request.created",
                target_type="credit_topup_request",
                target_id=request_id,
                payload={"user_id": user_id, "amount": request.amount},
            )
        return self.get_topup_request(request_id)

    def decide_topup_request(
        self,
        request_id: str,
        request: CloudCreditTopupDecisionRequest,
        *,
        actor: str,
    ) -> CloudCreditTopupRequestResponse:
        with connect(self.sqlite_path) as connection:
            row = self._get_topup_request_row(connection, request_id)
            if row["status"] != "pending":
                response = self._topup_request_response_from_row(row)
                return response.model_copy(update={"wallet": self._wallet_from_connection(connection, str(row["user_id"]))})

            now = utc_now()
            idempotency_key = request.idempotency_key or f"topup-request:{request_id}"
            wallet: WalletResponse | None = None
            if request.decision == "approved":
                wallet = self._topup_user_in_connection(
                    connection,
                    str(row["user_id"]),
                    amount=int(row["amount"]),
                    idempotency_key=idempotency_key,
                    note=request.note or row["note"],
                )
            connection.execute(
                """
                UPDATE credit_topup_requests
                SET status = ?, note = COALESCE(?, note), decided_by = ?,
                    topup_idempotency_key = ?, updated_at = ?, decided_at = ?
                WHERE id = ?
                """,
                (request.decision, request.note, actor, idempotency_key, now, now, request_id),
            )
            self._record_admin_audit(
                connection,
                actor=actor,
                action=f"credit_topup_request.{request.decision}",
                target_type="credit_topup_request",
                target_id=request_id,
                payload={"user_id": str(row["user_id"]), "amount": int(row["amount"])},
            )
        response = self.get_topup_request(request_id)
        return response.model_copy(update={"wallet": wallet}) if wallet is not None else response

    def get_topup_request(self, request_id: str) -> CloudCreditTopupRequestResponse:
        with connect(self.sqlite_path) as connection:
            row = self._get_topup_request_row(connection, request_id)
        return self._topup_request_response_from_row(row)

    def list_topup_requests(
        self,
        *,
        status_filter: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CloudCreditTopupRequestResponse]:
        safe_limit = min(max(limit, 1), 500)
        safe_offset = max(offset, 0)
        with connect(self.sqlite_path) as connection:
            if status_filter:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM credit_topup_requests
                    WHERE status = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (status_filter, safe_limit, safe_offset),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM credit_topup_requests
                    ORDER BY created_at DESC, id DESC
                    LIMIT ? OFFSET ?
                    """,
                    (safe_limit, safe_offset),
                ).fetchall()
        return [self._topup_request_response_from_row(row) for row in rows]

    def list_users(self, *, limit: int = 100, offset: int = 0) -> list[CloudUserAdminResponse]:
        safe_limit = min(max(limit, 1), 500)
        safe_offset = max(offset, 0)
        with connect(self.sqlite_path) as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM users
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (safe_limit, safe_offset),
            ).fetchall()
        users: list[CloudUserAdminResponse] = []
        for row in rows:
            user = self.get_user_admin(str(row["id"]))
            if user is not None:
                users.append(user)
        return users

    def get_user_by_email(self, email: str) -> CloudUserAdminResponse | None:
        normalized_email = _normalize_email(email)
        with connect(self.sqlite_path) as connection:
            row = connection.execute(
                "SELECT id FROM users WHERE email = ?",
                (normalized_email,),
            ).fetchone()
        if row is None:
            return None
        return self.get_user_admin(str(row["id"]))

    def update_user(self, user_id: str, request: CloudUserUpdateRequest) -> CloudUserAdminResponse:
        user = self.get_user_admin(user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")

        assignments: list[str] = []
        values: list[str | None] = []
        if request.password is not None:
            assignments.append("password_hash = ?")
            values.append(_hash_password(request.password))
        if request.display_name is not None:
            assignments.append("display_name = ?")
            values.append(request.display_name)
        if request.status is not None:
            assignments.append("status = ?")
            values.append(request.status)

        if assignments:
            assignments.append("updated_at = ?")
            values.append(utc_now())
            values.append(user_id)
            with connect(self.sqlite_path) as connection:
                connection.execute(
                    f"UPDATE users SET {', '.join(assignments)} WHERE id = ?",
                    tuple(values),
                )

        updated = self.get_user_admin(user_id)
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
        return updated

    def reserve_credits(self, user_id: str, request: CreditReservationRequest) -> CreditReservationResponse:
        with connect(self.sqlite_path) as connection:
            existing = connection.execute(
                """
                SELECT * FROM credit_reservations
                WHERE user_id = ? AND (job_id = ? OR idempotency_key = ?)
                """,
                (user_id, request.job_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                return self._reservation_response_from_row(existing)

            wallet = self.get_wallet(user_id)
            if wallet.available < request.units:
                raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="insufficient credits")

            reservation_id = str(uuid.uuid4())
            now = utc_now()
            connection.execute(
                """
                INSERT INTO credit_reservations (
                    id, user_id, job_id, module, status, units_reserved, units_captured,
                    units_released, idempotency_key, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 'active', ?, 0, 0, ?, ?, ?)
                """,
                (
                    reservation_id,
                    user_id,
                    request.job_id,
                    request.module,
                    request.units,
                    request.idempotency_key,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO credit_transactions (
                    id, user_id, type, amount, reservation_id, job_id, module,
                    idempotency_key, note, created_at
                )
                VALUES (?, ?, 'reserve', ?, ?, ?, ?, ?, NULL, ?)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    request.units,
                    reservation_id,
                    request.job_id,
                    request.module,
                    request.idempotency_key,
                    now,
                ),
            )
        return self.get_reservation(user_id, reservation_id)

    def capture_credits(
        self,
        user_id: str,
        reservation_id: str,
        request: CreditCaptureRequest,
    ) -> CreditReservationResponse:
        with connect(self.sqlite_path) as connection:
            row = self._get_reservation_row(connection, user_id, reservation_id)
            target_captured = min(int(request.units), int(row["units_reserved"]) - int(row["units_released"]))
            current_captured = int(row["units_captured"])
            delta = max(target_captured - current_captured, 0)
            if delta > 0:
                now = utc_now()
                connection.execute(
                    "UPDATE wallets SET balance = balance - ?, updated_at = ? WHERE user_id = ?",
                    (delta, now, user_id),
                )
                connection.execute(
                    """
                    UPDATE credit_reservations
                    SET units_captured = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (target_captured, now, reservation_id, user_id),
                )
                connection.execute(
                    """
                    INSERT INTO credit_transactions (
                        id, user_id, type, amount, reservation_id, job_id, module,
                        idempotency_key, note, created_at
                    )
                    VALUES (?, ?, 'capture', ?, ?, ?, ?, ?, NULL, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        delta,
                        reservation_id,
                        row["job_id"],
                        row["module"],
                        request.idempotency_key,
                        now,
                    ),
                )
            self._sync_reservation_status(connection, user_id, reservation_id)
        return self.get_reservation(user_id, reservation_id)

    def release_credits(
        self,
        user_id: str,
        reservation_id: str,
        request: CreditReleaseRequest,
    ) -> CreditReservationResponse:
        with connect(self.sqlite_path) as connection:
            row = self._get_reservation_row(connection, user_id, reservation_id)
            max_releasable = int(row["units_reserved"]) - int(row["units_captured"])
            target_released = min(int(request.units), max_releasable)
            current_released = int(row["units_released"])
            delta = max(target_released - current_released, 0)
            if delta > 0:
                now = utc_now()
                connection.execute(
                    """
                    UPDATE credit_reservations
                    SET units_released = ?, updated_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (target_released, now, reservation_id, user_id),
                )
                connection.execute(
                    """
                    INSERT INTO credit_transactions (
                        id, user_id, type, amount, reservation_id, job_id, module,
                        idempotency_key, note, created_at
                    )
                    VALUES (?, ?, 'release', ?, ?, ?, ?, ?, NULL, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        delta,
                        reservation_id,
                        row["job_id"],
                        row["module"],
                        request.idempotency_key,
                        now,
                    ),
                )
            self._sync_reservation_status(connection, user_id, reservation_id)
        return self.get_reservation(user_id, reservation_id)

    def get_reservation(self, user_id: str, reservation_id: str) -> CreditReservationResponse:
        with connect(self.sqlite_path) as connection:
            row = self._get_reservation_row(connection, user_id, reservation_id)
        return self._reservation_response_from_row(row)

    def list_ledger(self, user_id: str) -> list[CreditLedgerEntry]:
        with connect(self.sqlite_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM credit_transactions
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            CreditLedgerEntry(
                transaction_id=str(row["id"]),
                type=row["type"],
                amount=int(row["amount"]),
                reservation_id=row["reservation_id"],
                job_id=row["job_id"],
                module=row["module"],
                note=row["note"],
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def get_user_admin(self, user_id: str) -> CloudUserAdminResponse | None:
        with connect(self.sqlite_path) as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return CloudUserAdminResponse(
            user_id=str(row["id"]),
            email=str(row["email"]),
            display_name=row["display_name"],
            status=cast(CloudAccountStatus, row["status"]),
            wallet=self.get_wallet(str(row["id"])),
        )

    def _get_reservation_row(
        self,
        connection: sqlite3.Connection,
        user_id: str,
        reservation_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT *
            FROM credit_reservations
            WHERE user_id = ? AND id = ?
            """,
            (user_id, reservation_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reservation not found")
        return cast(sqlite3.Row, row)

    def _get_topup_request_row(self, connection: sqlite3.Connection, request_id: str) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT *
            FROM credit_topup_requests
            WHERE id = ?
            """,
            (request_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="topup request not found")
        return cast(sqlite3.Row, row)

    def _topup_user_in_connection(
        self,
        connection: sqlite3.Connection,
        user_id: str,
        *,
        amount: int,
        idempotency_key: str,
        note: str | None,
    ) -> WalletResponse:
        existing = connection.execute(
            """
            SELECT 1 FROM credit_transactions
            WHERE user_id = ? AND idempotency_key = ?
            """,
            (user_id, idempotency_key),
        ).fetchone()
        if existing is None:
            if connection.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
            now = utc_now()
            connection.execute(
                "UPDATE wallets SET balance = balance + ?, updated_at = ? WHERE user_id = ?",
                (amount, now, user_id),
            )
            connection.execute(
                """
                INSERT INTO credit_transactions (
                    id, user_id, type, amount, reservation_id, job_id, module,
                    idempotency_key, note, created_at
                )
                VALUES (?, ?, 'topup', ?, NULL, NULL, NULL, ?, ?, ?)
                """,
                (str(uuid.uuid4()), user_id, amount, idempotency_key, note, now),
            )
        return self._wallet_from_connection(connection, user_id)

    def _wallet_from_connection(self, connection: sqlite3.Connection, user_id: str) -> WalletResponse:
        row = connection.execute("SELECT balance FROM wallets WHERE user_id = ?", (user_id,)).fetchone()
        reserved_row = connection.execute(
            """
            SELECT COALESCE(SUM(units_reserved - units_captured - units_released), 0) AS reserved
            FROM credit_reservations
            WHERE user_id = ? AND status = 'active'
            """,
            (user_id,),
        ).fetchone()
        balance = int(row["balance"]) if row is not None else 0
        reserved = int(reserved_row["reserved"]) if reserved_row is not None else 0
        return WalletResponse(user_id=user_id, balance=balance, reserved=reserved, available=max(balance - reserved, 0))

    def _record_admin_audit(
        self,
        connection: sqlite3.Connection,
        *,
        actor: str,
        action: str,
        target_type: str | None,
        target_id: str | None,
        payload: dict[str, object],
    ) -> None:
        connection.execute(
            """
            INSERT INTO admin_audit_log (id, actor, action, target_type, target_id, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                actor,
                action,
                target_type,
                target_id,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                utc_now(),
            ),
        )

    def _topup_request_response_from_row(self, row: sqlite3.Row) -> CloudCreditTopupRequestResponse:
        return CloudCreditTopupRequestResponse(
            request_id=str(row["id"]),
            user_id=str(row["user_id"]),
            amount=int(row["amount"]),
            status=cast(CreditTopupRequestStatus, row["status"]),
            note=row["note"],
            payment_reference=row["payment_reference"],
            requested_by=str(row["requested_by"]),
            decided_by=row["decided_by"],
            topup_idempotency_key=row["topup_idempotency_key"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            decided_at=row["decided_at"],
        )

    def _sync_reservation_status(
        self,
        connection: sqlite3.Connection,
        user_id: str,
        reservation_id: str,
    ) -> None:
        row = self._get_reservation_row(connection, user_id, reservation_id)
        reserved = int(row["units_reserved"])
        captured = int(row["units_captured"])
        released = int(row["units_released"])
        next_status = "active"
        if captured + released >= reserved:
            next_status = "captured" if captured > 0 else "released"
        connection.execute(
            "UPDATE credit_reservations SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (next_status, utc_now(), reservation_id, user_id),
        )

    def _reservation_response_from_row(self, row: sqlite3.Row) -> CreditReservationResponse:
        return CreditReservationResponse(
            reservation_id=str(row["id"]),
            job_id=str(row["job_id"]),
            module=str(row["module"]),
            status=cast(CreditReservationStatus, row["status"]),
            units_reserved=int(row["units_reserved"]),
            units_captured=int(row["units_captured"]),
            units_released=int(row["units_released"]),
            wallet=self.get_wallet(str(row["user_id"])),
        )


def module_catalog_response() -> ModuleCatalogResponse:
    return ModuleCatalogResponse(modules=list(MODULE_CATALOG))
