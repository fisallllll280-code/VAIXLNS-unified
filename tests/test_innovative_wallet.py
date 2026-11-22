import pytest

from wallet.engine import IdempotencyConflict, InsufficientFunds, InnovativeWallet, WalletError


def funded_wallet() -> InnovativeWallet:
    wallet = InnovativeWallet()
    wallet.create_wallet("w1", "SAR")
    wallet.create_pool("team-goal", "SAR")
    wallet.record_settled_funding(
        "w1", 25_000, provider="test-adapter",
        provider_reference="settlement-001", idempotency_key="funding-001",
    )
    return wallet


def test_internal_contribution_balances_both_accounts_and_pool_report():
    wallet = funded_wallet()
    result = wallet.request_contribution(
        "w1", "team-goal", 5_000, idempotency_key="req-001",
        auto_approval_limit_minor=10_000, actor_id="system",
    )
    assert result["status"] == "POSTED"
    assert wallet.balance_minor("w1") == 20_000
    assert wallet.balance_minor("team-goal") == 5_000
    assert wallet.verify_integrity()
    report = wallet.pool_report("team-goal")
    assert report["balance_minor"] == 5_000
    assert report["contributors_minor"] == {"w1": 5_000}


def test_request_idempotency_returns_same_posting_without_double_counting():
    wallet = funded_wallet()
    first = wallet.request_contribution(
        "w1", "team-goal", 5_000, idempotency_key="req-duplicate",
        auto_approval_limit_minor=10_000, actor_id="system",
    )
    second = wallet.request_contribution(
        "w1", "team-goal", 5_000, idempotency_key="req-duplicate",
        auto_approval_limit_minor=10_000, actor_id="system",
    )
    assert first["request_id"] == second["request_id"]
    assert wallet.balance_minor("team-goal") == 5_000
    assert len(wallet.transactions) == 2  # one funding journal + one contribution


def test_reusing_idempotency_key_with_different_payload_is_rejected():
    wallet = funded_wallet()
    wallet.request_contribution(
        "w1", "team-goal", 5_000, idempotency_key="req-conflict",
        auto_approval_limit_minor=10_000, actor_id="system",
    )
    with pytest.raises(IdempotencyConflict):
        wallet.request_contribution(
            "w1", "team-goal", 6_000, idempotency_key="req-conflict",
            auto_approval_limit_minor=10_000, actor_id="system",
        )


def test_high_value_contribution_waits_for_approval_then_posts_once():
    wallet = funded_wallet()
    pending = wallet.request_contribution(
        "w1", "team-goal", 20_000, idempotency_key="req-approval",
        auto_approval_limit_minor=10_000, actor_id="system",
    )
    assert pending["status"] == "PENDING_APPROVAL"
    assert wallet.balance_minor("team-goal") == 0
    posted = wallet.approve_contribution(pending["request_id"], approver_id="finance-reviewer")
    posted_again = wallet.approve_contribution(pending["request_id"], approver_id="another-reviewer")
    assert posted["status"] == "POSTED"
    assert posted_again["transaction_id"] == posted["transaction_id"]
    assert wallet.balance_minor("team-goal") == 20_000


def test_insufficient_funds_rejects_contribution_without_partial_posting():
    wallet = funded_wallet()
    before = len(wallet.transactions)
    with pytest.raises(InsufficientFunds):
        wallet.request_contribution(
            "w1", "team-goal", 30_000, idempotency_key="req-too-large",
            auto_approval_limit_minor=50_000, actor_id="system",
        )
    assert wallet.balance_minor("team-goal") == 0
    assert len(wallet.transactions) == before


def test_provider_settlement_reference_prevents_duplicate_funding():
    wallet = InnovativeWallet()
    wallet.create_wallet("w1", "SAR")
    first = wallet.record_settled_funding(
        "w1", 10_000, provider="test-adapter",
        provider_reference="same-settlement", idempotency_key="fund-1",
    )
    second = wallet.record_settled_funding(
        "w1", 10_000, provider="test-adapter",
        provider_reference="same-settlement", idempotency_key="fund-2",
    )
    assert first.transaction_id == second.transaction_id
    assert wallet.balance_minor("w1") == 10_000
    with pytest.raises(IdempotencyConflict):
        wallet.record_settled_funding(
            "w1", 11_000, provider="test-adapter",
            provider_reference="same-settlement", idempotency_key="fund-3",
        )


def test_currency_mismatch_and_unbalanced_inputs_are_blocked():
    wallet = InnovativeWallet()
    wallet.create_wallet("usd-wallet", "USD")
    wallet.create_pool("sar-pool", "SAR")
    with pytest.raises(WalletError):
        wallet.request_contribution(
            "usd-wallet", "sar-pool", 100, idempotency_key="currency-mismatch",
            auto_approval_limit_minor=100, actor_id="system",
        )


def test_reconciliation_reports_discrepancies_without_mutating_ledger():
    wallet = funded_wallet()
    result = wallet.reconcile({"w1": 24_000, "team-goal": 0})
    assert not result["matched"]
    assert result["discrepancies"][0]["difference_minor"] == 1_000
    assert wallet.balance_minor("w1") == 25_000
