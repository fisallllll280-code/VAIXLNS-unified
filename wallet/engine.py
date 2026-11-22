"""Deterministic internal wallet ledger and contribution workflow.

Amounts are integer minor units (e.g. halalas/cents), never binary floats.
This module records internal accounting only; it does not connect to banks or
payment providers and must only record funding after a provider confirms settlement.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import uuid
from typing import Any


class WalletError(ValueError):
    """Base class for expected wallet errors."""


class IdempotencyConflict(WalletError):
    """An idempotency/reference key was reused for different parameters."""


class InsufficientFunds(WalletError):
    """A wallet does not have enough available balance."""


class ApprovalRequired(WalletError):
    """A contribution needs approval before it can be posted."""


@dataclass(frozen=True)
class Account:
    account_id: str
    currency: str
    kind: str  # wallet, pool, or clearing


@dataclass(frozen=True)
class Posting:
    account_id: str
    side: str  # DEBIT or CREDIT
    amount_minor: int


@dataclass(frozen=True)
class LedgerTransaction:
    transaction_id: str
    idempotency_key: str
    kind: str
    currency: str
    postings: tuple[Posting, ...]
    reference: str
    created_at: str
    metadata: tuple[tuple[str, str], ...]

    def metadata_dict(self) -> dict[str, str]:
        return dict(self.metadata)


class InnovativeWallet:
    """In-memory reference implementation of a balanced internal wallet ledger.

    A production deployment must replace the in-memory store with durable
    database transactions and uniqueness constraints before handling value.
    """

    def __init__(self) -> None:
        self._accounts: dict[str, Account] = {}
        self._transactions: list[LedgerTransaction] = []
        self._transactions_by_key: dict[str, tuple[str, LedgerTransaction]] = {}
        self._settlement_refs: dict[tuple[str, str], tuple[str, LedgerTransaction]] = {}
        self._requests: dict[str, dict[str, Any]] = {}
        self._request_keys: dict[str, tuple[str, str]] = {}

    @staticmethod
    def _currency(currency: str) -> str:
        if not isinstance(currency, str) or len(currency.strip()) != 3:
            raise WalletError("currency must be a three-letter code such as SAR or USD")
        return currency.strip().upper()

    @staticmethod
    def _positive_amount(amount_minor: int) -> int:
        if isinstance(amount_minor, bool) or not isinstance(amount_minor, int) or amount_minor <= 0:
            raise WalletError("amount_minor must be a positive integer")
        return amount_minor

    @staticmethod
    def _fingerprint(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(raw.encode("utf-8")).hexdigest()

    def _register_account(self, account_id: str, currency: str, kind: str) -> Account:
        if not account_id or not isinstance(account_id, str):
            raise WalletError("account_id is required")
        currency = self._currency(currency)
        existing = self._accounts.get(account_id)
        if existing:
            if existing.currency != currency or existing.kind != kind:
                raise WalletError("account already exists with different currency or kind")
            return existing
        account = Account(account_id=account_id, currency=currency, kind=kind)
        self._accounts[account_id] = account
        return account

    def create_wallet(self, wallet_id: str, currency: str = "SAR") -> Account:
        return self._register_account(wallet_id, currency, "wallet")

    def create_pool(self, pool_id: str, currency: str = "SAR") -> Account:
        return self._register_account(pool_id, currency, "pool")

    def account(self, account_id: str) -> Account:
        try:
            return self._accounts[account_id]
        except KeyError as exc:
            raise WalletError(f"unknown account: {account_id}") from exc

    def _balance_from_transactions(self, account_id: str) -> int:
        total = 0
        for transaction in self._transactions:
            for posting in transaction.postings:
                if posting.account_id == account_id:
                    total += posting.amount_minor if posting.side == "DEBIT" else -posting.amount_minor
        return total

    def balance_minor(self, account_id: str) -> int:
        self.account(account_id)
        return self._balance_from_transactions(account_id)

    def _post(
        self,
        *,
        idempotency_key: str,
        kind: str,
        currency: str,
        postings: tuple[Posting, ...],
        reference: str,
        metadata: dict[str, str] | None = None,
    ) -> LedgerTransaction:
        if not idempotency_key:
            raise WalletError("idempotency_key is required")
        currency = self._currency(currency)
        metadata = metadata or {}
        canonical_postings = [
            {"account_id": p.account_id, "side": p.side, "amount_minor": p.amount_minor}
            for p in postings
        ]
        fingerprint_payload = {
            "kind": kind,
            "currency": currency,
            "postings": canonical_postings,
            "reference": reference,
            "metadata": metadata,
        }
        fingerprint = self._fingerprint(fingerprint_payload)
        previous = self._transactions_by_key.get(idempotency_key)
        if previous:
            if previous[0] != fingerprint:
                raise IdempotencyConflict("idempotency key was reused with different transaction data")
            return previous[1]

        if not postings:
            raise WalletError("a transaction must contain postings")
        debit_total = 0
        credit_total = 0
        deltas: dict[str, int] = {}
        for posting in postings:
            if posting.side not in {"DEBIT", "CREDIT"}:
                raise WalletError("posting side must be DEBIT or CREDIT")
            self._positive_amount(posting.amount_minor)
            account = self.account(posting.account_id)
            if account.currency != currency:
                raise WalletError("all posting accounts must use the transaction currency")
            if posting.side == "DEBIT":
                debit_total += posting.amount_minor
                deltas[posting.account_id] = deltas.get(posting.account_id, 0) + posting.amount_minor
            else:
                credit_total += posting.amount_minor
                deltas[posting.account_id] = deltas.get(posting.account_id, 0) - posting.amount_minor
        if debit_total != credit_total:
            raise WalletError("double-entry transaction is not balanced")

        for account_id, delta in deltas.items():
            account = self.account(account_id)
            if account.kind in {"wallet", "pool"}:
                if self._balance_from_transactions(account_id) + delta < 0:
                    raise InsufficientFunds(f"insufficient balance in account {account_id}")

        transaction = LedgerTransaction(
            transaction_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            kind=kind,
            currency=currency,
            postings=postings,
            reference=reference,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=tuple(sorted((str(k), str(v)) for k, v in metadata.items())),
        )
        self._transactions.append(transaction)
        self._transactions_by_key[idempotency_key] = (fingerprint, transaction)
        return transaction

    def record_settled_funding(
        self,
        wallet_id: str,
        amount_minor: int,
        *,
        provider: str,
        provider_reference: str,
        idempotency_key: str,
    ) -> LedgerTransaction:
        """Record a deposit already confirmed as settled by a trusted provider.

        This method does not initiate or verify a payment. The caller must
        validate the provider webhook/signature and settlement status first.
        """
        amount_minor = self._positive_amount(amount_minor)
        if not provider or not provider_reference:
            raise WalletError("provider and provider_reference are required")
        wallet = self.account(wallet_id)
        if wallet.kind != "wallet":
            raise WalletError("funding target must be a wallet")
        settlement_key = (provider, provider_reference)
        payload = {
            "wallet_id": wallet_id,
            "amount_minor": amount_minor,
            "currency": wallet.currency,
            "provider": provider,
            "provider_reference": provider_reference,
        }
        fingerprint = self._fingerprint(payload)
        prior_settlement = self._settlement_refs.get(settlement_key)
        if prior_settlement:
            if prior_settlement[0] != fingerprint:
                raise IdempotencyConflict("provider reference reused for different funding data")
            return prior_settlement[1]

        clearing_id = f"clearing:{provider}:{wallet.currency}"
        self._register_account(clearing_id, wallet.currency, "clearing")
        transaction = self._post(
            idempotency_key=idempotency_key,
            kind="SETTLED_FUNDING",
            currency=wallet.currency,
            postings=(
                Posting(wallet_id, "DEBIT", amount_minor),
                Posting(clearing_id, "CREDIT", amount_minor),
            ),
            reference=provider_reference,
            metadata={"wallet_id": wallet_id, "provider": provider, "provider_reference": provider_reference},
        )
        self._settlement_refs[settlement_key] = (fingerprint, transaction)
        return transaction

    def _contribute(
        self,
        wallet_id: str,
        pool_id: str,
        amount_minor: int,
        *,
        idempotency_key: str,
        request_id: str,
        actor_id: str,
    ) -> LedgerTransaction:
        amount_minor = self._positive_amount(amount_minor)
        wallet = self.account(wallet_id)
        pool = self.account(pool_id)
        if wallet.kind != "wallet" or pool.kind != "pool":
            raise WalletError("contribution must move from a wallet to a pool")
        if wallet.currency != pool.currency:
            raise WalletError("wallet and pool currencies must match")
        return self._post(
            idempotency_key=idempotency_key,
            kind="POOL_CONTRIBUTION",
            currency=wallet.currency,
            postings=(
                Posting(wallet_id, "CREDIT", amount_minor),
                Posting(pool_id, "DEBIT", amount_minor),
            ),
            reference=request_id,
            metadata={
                "source_wallet_id": wallet_id,
                "pool_id": pool_id,
                "request_id": request_id,
                "actor_id": actor_id,
            },
        )

    def request_contribution(
        self,
        wallet_id: str,
        pool_id: str,
        amount_minor: int,
        *,
        idempotency_key: str,
        auto_approval_limit_minor: int,
        actor_id: str,
    ) -> dict[str, Any]:
        """Submit a contribution, auto-posting only within an explicit policy limit."""
        amount_minor = self._positive_amount(amount_minor)
        if isinstance(auto_approval_limit_minor, bool) or not isinstance(auto_approval_limit_minor, int) or auto_approval_limit_minor < 0:
            raise WalletError("auto_approval_limit_minor must be a non-negative integer")
        if not idempotency_key or not actor_id:
            raise WalletError("idempotency_key and actor_id are required")
        wallet = self.account(wallet_id)
        pool = self.account(pool_id)
        if wallet.kind != "wallet" or pool.kind != "pool":
            raise WalletError("contribution must move from a wallet to a pool")
        if wallet.currency != pool.currency:
            raise WalletError("wallet and pool currencies must match")

        payload = {
            "wallet_id": wallet_id,
            "pool_id": pool_id,
            "amount_minor": amount_minor,
            "auto_approval_limit_minor": auto_approval_limit_minor,
            "actor_id": actor_id,
        }
        fingerprint = self._fingerprint(payload)
        prior = self._request_keys.get(idempotency_key)
        if prior:
            if prior[0] != fingerprint:
                raise IdempotencyConflict("workflow idempotency key reused with different request data")
            return dict(self._requests[prior[1]])

        request_id = str(uuid.uuid4())
        request = {
            "request_id": request_id,
            "idempotency_key": idempotency_key,
            "wallet_id": wallet_id,
            "pool_id": pool_id,
            "amount_minor": amount_minor,
            "currency": wallet.currency,
            "actor_id": actor_id,
            "status": "PENDING_APPROVAL",
            "transaction_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": None,
        }
        if amount_minor <= auto_approval_limit_minor:
            transaction = self._contribute(
                wallet_id,
                pool_id,
                amount_minor,
                idempotency_key=f"contribution:{idempotency_key}",
                request_id=request_id,
                actor_id=actor_id,
            )
            request["status"] = "POSTED"
            request["transaction_id"] = transaction.transaction_id
        self._requests[request_id] = request
        self._request_keys[idempotency_key] = (fingerprint, request_id)
        return dict(request)

    def approve_contribution(self, request_id: str, *, approver_id: str) -> dict[str, Any]:
        """Approve a pending internal contribution; balance is rechecked at posting time."""
        if not approver_id:
            raise WalletError("approver_id is required")
        try:
            request = self._requests[request_id]
        except KeyError as exc:
            raise WalletError(f"unknown contribution request: {request_id}") from exc
        if request["status"] == "POSTED":
            return dict(request)
        if request["status"] != "PENDING_APPROVAL":
            raise WalletError(f"request cannot be approved from state {request['status']}")
        transaction = self._contribute(
            request["wallet_id"],
            request["pool_id"],
            request["amount_minor"],
            idempotency_key=f"approval:{request_id}",
            request_id=request_id,
            actor_id=approver_id,
        )
        request["status"] = "POSTED"
        request["transaction_id"] = transaction.transaction_id
        request["approved_by"] = approver_id
        request["approved_at"] = datetime.now(timezone.utc).isoformat()
        return dict(request)

    def pool_report(self, pool_id: str) -> dict[str, Any]:
        pool = self.account(pool_id)
        if pool.kind != "pool":
            raise WalletError("account is not a pool")
        contributions: dict[str, int] = {}
        for transaction in self._transactions:
            metadata = transaction.metadata_dict()
            if transaction.kind == "POOL_CONTRIBUTION" and metadata.get("pool_id") == pool_id:
                owner = metadata["source_wallet_id"]
                contributions[owner] = contributions.get(owner, 0) + next(
                    p.amount_minor for p in transaction.postings if p.account_id == pool_id and p.side == "DEBIT"
                )
        return {
            "pool_id": pool_id,
            "currency": pool.currency,
            "balance_minor": self.balance_minor(pool_id),
            "contributors_minor": dict(sorted(contributions.items())),
            "contribution_count": sum(1 for t in self._transactions if t.kind == "POOL_CONTRIBUTION" and t.metadata_dict().get("pool_id") == pool_id),
        }

    def reconcile(self, externally_reported_balances_minor: dict[str, int]) -> dict[str, Any]:
        """Compare selected external balance snapshots with ledger-derived balances."""
        discrepancies = []
        for account_id, reported in externally_reported_balances_minor.items():
            if isinstance(reported, bool) or not isinstance(reported, int):
                raise WalletError("reported balances must use integer minor units")
            self.account(account_id)
            ledger_balance = self.balance_minor(account_id)
            if ledger_balance != reported:
                discrepancies.append({
                    "account_id": account_id,
                    "ledger_balance_minor": ledger_balance,
                    "reported_balance_minor": reported,
                    "difference_minor": ledger_balance - reported,
                })
        return {"matched": not discrepancies, "discrepancies": discrepancies}

    def verify_integrity(self) -> bool:
        """Check every transaction balances and each wallet/pool remains non-negative."""
        running: dict[str, int] = {account_id: 0 for account_id in self._accounts}
        for transaction in self._transactions:
            debit_total = sum(p.amount_minor for p in transaction.postings if p.side == "DEBIT")
            credit_total = sum(p.amount_minor for p in transaction.postings if p.side == "CREDIT")
            if debit_total != credit_total:
                return False
            for posting in transaction.postings:
                running.setdefault(posting.account_id, 0)
                running[posting.account_id] += posting.amount_minor if posting.side == "DEBIT" else -posting.amount_minor
                account = self._accounts.get(posting.account_id)
                if account and account.kind in {"wallet", "pool"} and running[posting.account_id] < 0:
                    return False
        return True

    @property
    def transactions(self) -> tuple[LedgerTransaction, ...]:
        return tuple(self._transactions)
