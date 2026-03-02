"""Unit tests for the AsyncMonzoClient class."""

import pytest
import respx
import json
import os
from unittest.mock import patch
from httpx import Response

from monzo.client import AsyncMonzoClient
from monzo.exceptions import (
    MonzoAPIError,
    MonzoAuthenticationError,
    MonzoRateLimitError,
    MonzoValidationError,
)
from monzo.models import Account, Balance, Pot, Transaction, Webhook, FeedItem

pytestmark = pytest.mark.asyncio


class TestAsyncMonzoClient:
    """Test cases for AsyncMonzoClient."""

    async def test_init_with_access_token(self):
        """Test client initialization with access token."""
        client = AsyncMonzoClient(access_token="test_token", auth_file="nonexistent.json", auto_save=False)
        assert client.access_token == "test_token"

    @respx.mock
    async def test_get_accounts_success(self):
        """Test successful account retrieval."""
        mock_response = {
            "accounts": [
                {
                    "id": "acc_123",
                    "name": "Test Account",
                    "currency": "GBP",
                    "balance": 1000,
                    "type": "uk_retail",
                    "description": "Test account",
                    "created": "2023-01-01T00:00:00Z",
                    "closed": False,
                }
            ]
        }
        respx.get("https://api.monzo.com/accounts").mock(return_value=Response(200, json=mock_response))

        async with AsyncMonzoClient(access_token="test_token") as client:
            accounts = await client.get_accounts()

        assert len(accounts) == 1
        account = accounts[0]
        assert isinstance(account, Account)
        assert account.id == "acc_123"
        assert account.balance == 1000

    @respx.mock
    async def test_get_balance_success(self):
        """Test successful balance retrieval."""
        mock_response = {
            "balance": 1000,
            "currency": "GBP",
            "spend_today": 50,
        }
        respx.get("https://api.monzo.com/balance").mock(return_value=Response(200, json=mock_response))

        async with AsyncMonzoClient(access_token="test_token") as client:
            balance = await client.get_balance("acc_123")

        assert isinstance(balance, Balance)
        assert balance.balance == 1000
        assert balance.spend_today == 50

    @respx.mock
    async def test_get_transactions_success(self):
        """Test successful transaction retrieval."""
        mock_response = {
            "transactions": [
                {
                    "id": "tx_123",
                    "amount": -500,
                    "currency": "GBP",
                    "description": "Test transaction",
                    "category": "general",
                    "created": "2023-01-01T00:00:00Z",
                }
            ]
        }
        respx.get("https://api.monzo.com/transactions").mock(return_value=Response(200, json=mock_response))

        async with AsyncMonzoClient(access_token="test_token") as client:
            transactions = await client.get_transactions("acc_123")

        assert len(transactions) == 1
        transaction = transactions[0]
        assert isinstance(transaction, Transaction)
        assert transaction.id == "tx_123"
        assert transaction.amount == -500

    @respx.mock
    async def test_create_webhook_success(self):
        """Test successful webhook creation."""
        mock_response = {
            "webhook": {
                "id": "webhook_123",
                "account_id": "acc_123",
                "url": "https://example.com/webhook",
                "type": "transaction.created",
                "created": "2023-01-01T00:00:00Z",
            }
        }
        # Webhook creation uses form data (x-www-form-urlencoded)
        respx.post("https://api.monzo.com/webhooks").mock(return_value=Response(200, json=mock_response))

        async with AsyncMonzoClient(access_token="test_token") as client:
            webhook = await client.create_webhook("acc_123", "https://example.com/webhook")

        assert isinstance(webhook, Webhook)
        assert webhook.id == "webhook_123"
        assert webhook.url == "https://example.com/webhook"

    @respx.mock
    async def test_authentication_error(self):
        """Test authentication error handling."""
        respx.get("https://api.monzo.com/accounts").mock(return_value=Response(401, json={"error": "unauthorized"}))

        async with AsyncMonzoClient(access_token="invalid_token") as client:
            with pytest.raises(MonzoAuthenticationError, match="Invalid access token"):
                await client.get_accounts()

    @respx.mock
    async def test_rate_limit_error(self):
        """Test rate limit error handling."""
        respx.get("https://api.monzo.com/accounts").mock(return_value=Response(429, json={"error": "rate_limited"}))

        # We set max_retries to 0 to avoid waiting in tests
        async with AsyncMonzoClient(access_token="test_token", max_retries=0) as client:
            with pytest.raises(MonzoRateLimitError, match="Rate limit exceeded"):
                await client.get_accounts()

    @respx.mock
    async def test_retry_logic_on_server_error(self):
        """Test retry logic on server errors."""
        # Mock 500 error then success
        route = respx.get("https://api.monzo.com/accounts")
        route.side_effect = [
            Response(500),
            Response(200, json={"accounts": []})
        ]

        async with AsyncMonzoClient(access_token="test_token", max_retries=1, retry_delay=0.01) as client:
            accounts = await client.get_accounts()
        
        assert accounts == []
        assert route.call_count == 2

    @respx.mock
    async def test_deposit_to_pot_success(self):
        """Test successful pot deposit."""
        respx.put(url__regex=r"https://api.monzo.com/pots/pot_123/deposit").mock(return_value=Response(200, json={"success": True}))

        async with AsyncMonzoClient(access_token="test_token") as client:
            response = await client.deposit_to_pot("pot_123", "acc_123", 1000)

        assert response["success"] is True

    @respx.mock
    async def test_withdraw_from_pot_success(self):
        """Test successful pot withdrawal."""
        respx.put(url__regex=r"https://api.monzo.com/pots/pot_123/withdraw").mock(return_value=Response(200, json={"success": True}))

        async with AsyncMonzoClient(access_token="test_token") as client:
            response = await client.withdraw_from_pot("pot_123", "acc_123", 500)

        assert response["success"] is True

    @respx.mock
    async def test_whoami_success(self):
        """Test successful whoami call."""
        mock_response = {
            "authenticated_user_id": "user_123",
            "client_id": "client_123",
        }
        respx.get("https://api.monzo.com/ping/whoami").mock(return_value=Response(200, json=mock_response))

        async with AsyncMonzoClient(access_token="test_token") as client:
            user_info = await client.whoami()

        assert user_info["authenticated_user_id"] == "user_123"

    @respx.mock
    async def test_get_transactions_with_pagination(self):
        """Test transaction retrieval with auto-pagination."""
        # First page response
        mock_response_1 = {
            "transactions": [
                {
                    "id": "tx_1",
                    "amount": -500,
                    "currency": "GBP",
                    "description": "Transaction 1",
                    "category": "general",
                    "created": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "tx_2",
                    "amount": -300,
                    "currency": "GBP",
                    "description": "Transaction 2",
                    "category": "general",
                    "created": "2023-01-01T00:00:01Z",
                }
            ]
        }
        # Second page response (empty, indicating end)
        mock_response_2 = {
            "transactions": []
        }
        
        # Mock the two calls
        respx.get("https://api.monzo.com/transactions", params={"account_id": "acc_123", "limit": "100"}).mock(return_value=Response(200, json=mock_response_1))
        respx.get("https://api.monzo.com/transactions", params={"account_id": "acc_123", "limit": "100", "since": "2023-01-01T00:00:02+00:00"}).mock(return_value=Response(200, json=mock_response_2))

        async with AsyncMonzoClient(access_token="test_token") as client:
            transactions = await client.get_transactions("acc_123")

        assert len(transactions) == 2
        assert transactions[0].id == "tx_1"
        assert transactions[1].id == "tx_2"
