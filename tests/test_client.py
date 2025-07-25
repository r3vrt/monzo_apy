"""Unit tests for the MonzoClient class."""

from unittest.mock import patch

import pytest
import responses
import tempfile
import os

from monzo.client import MonzoClient
from monzo.exceptions import (
    MonzoAPIError,
    MonzoAuthenticationError,
    MonzoRateLimitError,
    MonzoValidationError,
)
from monzo.models import Account, Balance, Pot, Transaction, Webhook, FeedItem


class TestMonzoClient:
    """Test cases for MonzoClient."""

    def test_init_with_access_token(self):
        """Test client initialization with access token."""
        client = MonzoClient(access_token="test_token", auth_file="nonexistent.json", auto_save=False)
        assert client.access_token == "test_token"
        assert client.session.headers["Authorization"] == "Bearer test_token"

    @patch.dict("os.environ", {"MONZO_ACCESS_TOKEN": "env_token"})
    def test_init_with_env_token(self):
        """Test client initialization with environment variable."""
        client = MonzoClient(auth_file="nonexistent.json", auto_save=False)
        assert client.access_token == "env_token"

    def test_init_without_token(self):
        """Test client initialization without token raises error."""
        client = MonzoClient(access_token=None, auth_file="nonexistent.json", auto_save=False)
        with pytest.raises(MonzoAuthenticationError, match="No access token provided"):
            client.get_accounts()  # This will trigger the authentication check

    @responses.activate
    def test_get_accounts_success(self):
        """Test successful account retrieval."""
        # Mock API response
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
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        accounts = client.get_accounts()

        assert len(accounts) == 1
        account = accounts[0]
        assert isinstance(account, Account)
        assert account.id == "acc_123"
        assert account.name == "Test Account"
        assert account.balance == 1000
        assert account.currency == "GBP"

    @responses.activate
    def test_get_account_success(self):
        """Test successful single account retrieval."""
        mock_response = {
            "account": {
                "id": "acc_123",
                "name": "Test Account",
                "currency": "GBP",
                "balance": 1000,
                "type": "uk_retail",
                "description": "Test account",
                "created": "2023-01-01T00:00:00Z",
                "closed": False,
            }
        }
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts/acc_123",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        account = client.get_account("acc_123")

        assert isinstance(account, Account)
        assert account.id == "acc_123"
        assert account.name == "Test Account"

    @responses.activate
    def test_get_balance_success(self):
        """Test successful balance retrieval."""
        mock_response = {
            "balance": 1000,
            "currency": "GBP",
            "spend_today": 50,
            "local_currency": "GBP",
            "local_exchange_rate": 1.0,
            "local_spend": [],
        }
        responses.add(
            responses.GET,
            "https://api.monzo.com/balance?account_id=acc_123",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        balance = client.get_balance("acc_123")

        assert isinstance(balance, Balance)
        assert balance.balance == 1000
        assert balance.currency == "GBP"
        assert balance.spend_today == 50

    @responses.activate
    def test_get_transactions_success(self):
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
                    "settled": "2023-01-01T00:00:00Z",
                    "account_balance": 1000,
                }
            ]
        }
        responses.add(
            responses.GET,
            "https://api.monzo.com/transactions?account_id=acc_123",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        transactions = client.get_transactions("acc_123")

        assert len(transactions) == 1
        transaction = transactions[0]
        assert isinstance(transaction, Transaction)
        assert transaction.id == "tx_123"
        assert transaction.amount == -500
        assert transaction.description == "Test transaction"

    @responses.activate
    def test_get_transactions_with_params(self):
        """Test transaction retrieval with query parameters."""
        mock_response = {"transactions": []}
        responses.add(
            responses.GET,
            (
                "https://api.monzo.com/transactions?"
                "account_id=acc_123&limit=10&since=2023-01-01T00:00:00Z"
            ),
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        transactions = client.get_transactions(
            "acc_123", limit=10, since="2023-01-01T00:00:00Z"
        )

        assert transactions == []

    @responses.activate
    def test_annotate_transaction_success(self):
        """Test successful transaction annotation."""
        mock_response = {
            "transaction": {
                "id": "tx_123",
                "amount": -500,
                "currency": "GBP",
                "description": "Test transaction",
                "category": "general",
                "metadata": {"notes": "Test note"},
            }
        }
        responses.add(
            responses.PATCH,
            "https://api.monzo.com/transactions/tx_123",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        transaction = client.annotate_transaction("tx_123", {"notes": "Test note"})

        assert isinstance(transaction, Transaction)
        assert transaction.id == "tx_123"
        assert transaction.metadata == {"notes": "Test note"}

    @responses.activate
    def test_get_pots_success(self):
        """Test successful pot retrieval."""
        mock_response = {
            "pots": [
                {
                    "id": "pot_123",
                    "name": "Test Pot",
                    "balance": 500,
                    "currency": "GBP",
                    "style": "beach_ball",
                    "deleted": False,
                    "created": "2023-01-01T00:00:00Z",
                    "updated": "2023-01-01T00:00:00Z",
                }
            ]
        }
        responses.add(
            responses.GET,
            "https://api.monzo.com/pots?current_account_id=acc_123",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        pots = client.get_pots("acc_123")

        assert len(pots) == 1
        pot = pots[0]
        assert isinstance(pot, Pot)
        assert pot.id == "pot_123"
        assert pot.name == "Test Pot"
        assert pot.balance == 500

    @responses.activate
    def test_get_pots_by_name(self):
        """Test pot retrieval with name filtering."""
        mock_response = {
            "pots": [
                {
                    "id": "pot_123",
                    "name": "Test Pot",
                    "balance": 500,
                    "currency": "GBP",
                    "style": "beach_ball",
                    "deleted": False,
                    "created": "2023-01-01T00:00:00Z",
                    "updated": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "pot_456",
                    "name": "Main Pot",
                    "balance": 1000,
                    "currency": "GBP",
                    "style": "beach_ball",
                    "deleted": False,
                    "created": "2023-01-01T00:00:00Z",
                    "updated": "2023-01-01T00:00:00Z",
                }
            ]
        }
        responses.add(
            responses.GET,
            "https://api.monzo.com/pots?current_account_id=acc_123",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        
        # Test filtering by name
        test_pots = client.get_pots("acc_123", pot_name="Test")
        assert len(test_pots) == 1
        assert test_pots[0].name == "Test Pot"
        
        # Test case-insensitive search
        test_pots_case = client.get_pots("acc_123", pot_name="test")
        assert len(test_pots_case) == 1
        assert test_pots_case[0].name == "Test Pot"
        
        # Test partial match
        partial_pots = client.get_pots("acc_123", pot_name="Te")
        assert len(partial_pots) == 1
        assert partial_pots[0].name == "Test Pot"
        
        # Test non-existent pot
        non_existent = client.get_pots("acc_123", pot_name="NonExistent")
        assert non_existent == []

    @responses.activate
    def test_get_pot_by_name(self):
        """Test getting a pot by name."""
        mock_response = {
            "pots": [
                {
                    "id": "pot_123",
                    "name": "Side Pot",
                    "balance": 500,
                    "currency": "GBP",
                    "style": "beach_ball",
                    "deleted": False,
                    "created": "2023-01-01T00:00:00Z",
                    "updated": "2023-01-01T00:00:00Z",
                },
                {
                    "id": "pot_456",
                    "name": "Main Pot",
                    "balance": 1000,
                    "currency": "GBP",
                    "style": "beach_ball",
                    "deleted": False,
                    "created": "2023-01-01T00:00:00Z",
                    "updated": "2023-01-01T00:00:00Z",
                }
            ]
        }
        responses.add(
            responses.GET,
            "https://api.monzo.com/pots?current_account_id=acc_123",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        
        # Test exact match
        side_pot = client.get_pot_by_name("acc_123", "Side Pot")
        assert side_pot.id == "pot_123"
        assert side_pot.name == "Side Pot"
        
        # Test case-insensitive exact match
        side_pot_case = client.get_pot_by_name("acc_123", "side pot")
        assert side_pot_case.id == "pot_123"
        assert side_pot_case.name == "Side Pot"
        
        # Test non-existent pot raises ValueError
        with pytest.raises(ValueError, match="No pot found with name 'NonExistent'"):
            client.get_pot_by_name("acc_123", "NonExistent")

    @responses.activate
    def test_deposit_to_pot_success(self):
        """Test successful pot deposit."""
        mock_response = {"success": True}
        responses.add(
            responses.PUT,
            "https://api.monzo.com/pots/pot_123/deposit",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        response = client.deposit_to_pot("pot_123", "acc_123", 1000)

        assert response["success"] is True

    @responses.activate
    def test_withdraw_from_pot_success(self):
        """Test successful pot withdrawal."""
        mock_response = {"success": True}
        responses.add(
            responses.PUT,
            "https://api.monzo.com/pots/pot_123/withdraw",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        response = client.withdraw_from_pot("pot_123", "acc_123", 500)

        assert response["success"] is True

    @responses.activate
    def test_authentication_error(self):
        """Test authentication error handling."""
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts",
            json={"error": "unauthorized"},
            status=401,
        )

        client = MonzoClient(access_token="invalid_token")
        with pytest.raises(MonzoAuthenticationError, match="Invalid access token"):
            client.get_accounts()

    @responses.activate
    def test_rate_limit_error(self):
        """Test rate limit error handling."""
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts",
            json={"error": "rate_limited"},
            status=429,
        )

        client = MonzoClient(access_token="test_token")
        with pytest.raises(MonzoRateLimitError, match="Rate limit exceeded"):
            client.get_accounts()

    @responses.activate
    def test_validation_error(self):
        """Test validation error handling."""
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts/invalid_id",
            json={"error": "bad_request"},
            status=400,
        )

        client = MonzoClient(access_token="test_token")
        with pytest.raises(MonzoValidationError, match="Invalid request"):
            client.get_account("invalid_id")

    @responses.activate
    def test_generic_api_error(self):
        """Test generic API error handling."""
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts",
            json={"error": "server_error"},
            status=500,
        )

        client = MonzoClient(access_token="test_token")
        with pytest.raises(MonzoAPIError, match="API request failed: 500"):
            client.get_accounts()

    @responses.activate
    def test_whoami_success(self):
        """Test successful whoami call."""
        mock_response = {
            "authenticated_user_id": "user_123",
            "client_id": "client_123",
        }
        responses.add(
            responses.GET,
            "https://api.monzo.com/ping/whoami",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        user_info = client.whoami()

        assert user_info["authenticated_user_id"] == "user_123"
        assert user_info["client_id"] == "client_123"

    def test_save_and_load_auth(self):
        """Test saving and loading auth info to/from a temp file."""
        test_auth = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "redirect_uri": "http://localhost/callback",
        }
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            config_path = tmp.name
        # Create client and save auth
        client = MonzoClient(**test_auth, auto_save=False)
        client.save_auth(config_path)
        assert os.path.exists(config_path)
        # Create a new client and load auth
        client2 = MonzoClient(auth_file=config_path, auto_save=False)
        assert client2.access_token == test_auth["access_token"]
        assert client2.refresh_token == test_auth["refresh_token"]
        assert client2.client_id == test_auth["client_id"]
        assert client2.client_secret == test_auth["client_secret"]
        assert client2.redirect_uri == test_auth["redirect_uri"]
        # Clean up
        os.remove(config_path)

    @responses.activate
    def test_create_webhook_success(self):
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
        responses.add(
            responses.POST,
            "https://api.monzo.com/webhooks",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        webhook = client.create_webhook("acc_123", "https://example.com/webhook")

        assert isinstance(webhook, Webhook)
        assert webhook.id == "webhook_123"
        assert webhook.account_id == "acc_123"
        assert webhook.url == "https://example.com/webhook"
        assert webhook.webhook_type == "transaction.created"

    @responses.activate
    def test_list_webhooks_success(self):
        """Test successful webhook listing."""
        mock_response = {
            "webhooks": [
                {
                    "id": "webhook_123",
                    "account_id": "acc_123",
                    "url": "https://example.com/webhook",
                    "type": "transaction.created",
                    "created": "2023-01-01T00:00:00Z",
                }
            ]
        }
        responses.add(
            responses.GET,
            "https://api.monzo.com/webhooks?account_id=acc_123",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        webhooks = client.list_webhooks("acc_123")

        assert len(webhooks) == 1
        webhook = webhooks[0]
        assert isinstance(webhook, Webhook)
        assert webhook.id == "webhook_123"

    @responses.activate
    def test_delete_webhook_success(self):
        """Test successful webhook deletion."""
        responses.add(
            responses.DELETE,
            "https://api.monzo.com/webhooks/webhook_123",
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        client.delete_webhook("webhook_123")  # Should not raise an exception

    @responses.activate
    def test_create_feed_item_success(self):
        """Test successful feed item creation."""
        mock_response = {
            "feed_item": {
                "id": "feed_123",
                "account_id": "acc_123",
                "title": "Test Feed Item",
                "body": "This is a test feed item",
                "image_url": "https://example.com/image.jpg",
                "action_url": "https://example.com/action",
                "created": "2023-01-01T00:00:00Z",
            }
        }
        responses.add(
            responses.POST,
            "https://api.monzo.com/feed",
            json=mock_response,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        feed_item = client.create_feed_item(
            "acc_123",
            "Test Feed Item",
            "This is a test feed item",
            image_url="https://example.com/image.jpg",
            action_url="https://example.com/action"
        )

        assert isinstance(feed_item, FeedItem)
        assert feed_item.id == "created"
        assert feed_item.account_id == "acc_123"
        assert feed_item.title == "Test Feed Item"
        assert feed_item.body == "This is a test feed item"

    @responses.activate
    def test_get_transactions_with_pagination(self):
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
                },
                {
                    "id": "tx_2",
                    "amount": -300,
                    "currency": "GBP",
                    "description": "Transaction 2",
                    "category": "general",
                }
            ]
        }
        # Second page response (empty, indicating end)
        mock_response_2 = {
            "transactions": []
        }
        
        responses.add(
            responses.GET,
            "https://api.monzo.com/transactions?account_id=acc_123&limit=100",
            json=mock_response_1,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://api.monzo.com/transactions?account_id=acc_123&limit=100&since=tx_2",
            json=mock_response_2,
            status=200,
        )

        client = MonzoClient(access_token="test_token")
        transactions = client.get_transactions("acc_123", auto_paginate=True)

        assert len(transactions) == 2
        assert transactions[0].id == "tx_1"
        assert transactions[1].id == "tx_2"

    @responses.activate
    def test_retry_logic_on_rate_limit(self):
        """Test retry logic when rate limited."""
        # First request returns 429, second succeeds
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts",
            json={"error": "rate_limited"},
            status=429,
        )
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts",
            json={"accounts": [{"id": "acc_123", "name": "Test", "currency": "GBP", "balance": 1000, "type": "uk_retail"}]},
            status=200,
        )

        client = MonzoClient(access_token="test_token", max_retries=1, retry_delay=0.1)
        accounts = client.get_accounts()
        
        assert len(accounts) == 1
        assert accounts[0].id == "acc_123"

    @responses.activate
    def test_retry_logic_on_server_error(self):
        """Test retry logic on server errors."""
        # First request returns 500, second succeeds
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts",
            json={"error": "server_error"},
            status=500,
        )
        responses.add(
            responses.GET,
            "https://api.monzo.com/accounts",
            json={"accounts": [{"id": "acc_123", "name": "Test", "currency": "GBP", "balance": 1000, "type": "uk_retail"}]},
            status=200,
        )

        client = MonzoClient(access_token="test_token", max_retries=1, retry_delay=0.1)
        accounts = client.get_accounts()
        
        assert len(accounts) == 1
        assert accounts[0].id == "acc_123"

    @responses.activate
    def test_retry_logic_max_retries_exceeded(self):
        """Test that max retries are respected."""
        # All requests return 500
        for _ in range(4):  # 3 retries + 1 initial attempt
            responses.add(
                responses.GET,
                "https://api.monzo.com/accounts",
                json={"error": "server_error"},
                status=500,
            )

        client = MonzoClient(access_token="test_token", max_retries=3, retry_delay=0.1)
        
        with pytest.raises(MonzoAPIError, match="API request failed: 500"):
            client.get_accounts()

    @responses.activate
    def test_ensure_recent_authentication(self):
        """Test ensure_recent_authentication method."""
        client = MonzoClient(
            access_token="old_token",
            refresh_token="refresh_token",
            client_id="client_id",
            client_secret="client_secret",
            redirect_uri="http://localhost"
        )
        
        # Call the method - should raise ValueError with auth URL
        with pytest.raises(ValueError, match="Full reauthentication required"):
            client.ensure_recent_authentication()

    def test_ensure_recent_authentication_missing_credentials(self):
        """Test ensure_recent_authentication method with missing OAuth2 credentials."""
        client = MonzoClient(access_token="test_token")
        
        # Call the method - should raise ValueError about missing credentials
        with pytest.raises(ValueError, match="client_id, client_secret, and redirect_uri are required"):
            client.ensure_recent_authentication()

    def test_is_authentication_recent(self):
        """Test is_authentication_recent method."""
        client = MonzoClient(access_token="test_token")
        
        # This method currently always returns False as a safety measure
        assert client.is_authentication_recent() is False
        assert client.is_authentication_recent(max_age_minutes=10) is False

    @responses.activate
    def test_get_transactions_with_ensure_recent_auth(self):
        """Test get_transactions with ensure_recent_auth parameter."""
        client = MonzoClient(
            access_token="old_token",
            refresh_token="refresh_token",
            client_id="client_id",
            client_secret="client_secret",
            redirect_uri="http://localhost"
        )
        
        # Call get_transactions with ensure_recent_auth=True
        # This should raise ValueError because full reauthentication is required
        with pytest.raises(ValueError, match="Full reauthentication required"):
            client.get_transactions("acc_123", ensure_recent_auth=True)

    @responses.activate
    def test_perform_full_reauthentication(self):
        """Test perform_full_reauthentication method."""
        import tempfile
        # Mock token exchange response
        mock_exchange_response = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }
        responses.add(
            responses.POST,
            "https://api.monzo.com/oauth2/token",
            json=mock_exchange_response,
            status=200,
        )
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            auth_path = tmp.name
        client = MonzoClient(
            access_token="old_token",
            refresh_token="refresh_token",
            client_id="client_id",
            client_secret="client_secret",
            redirect_uri="http://localhost",
            auth_file=auth_path,
            auto_save=True,
        )
        # Perform full reauthentication
        tokens = client.perform_full_reauthentication("auth_code_123")
        # Verify that tokens were updated
        assert client.access_token == "new_access_token"
        assert client.refresh_token == "new_refresh_token"
        assert tokens == mock_exchange_response
        import os
        os.remove(auth_path)

    @responses.activate
    def test_upload_attachment_success(self):
        """Test successful upload_attachment (get upload URL)."""
        mock_response = {
            "upload_url": "https://uploads.monzo.com/upload/abc123",
            "file_url": "https://files.monzo.com/file/abc123.jpg"
        }
        responses.add(
            responses.POST,
            "https://api.monzo.com/attachment/upload",
            json=mock_response,
            status=200,
        )
        client = MonzoClient(access_token="test_token")
        result = client.upload_attachment(file_type="image/jpeg")
        assert result["upload_url"] == mock_response["upload_url"]
        assert result["file_url"] == mock_response["file_url"]

    @responses.activate
    def test_register_attachment_success(self):
        """Test successful register_attachment."""
        mock_response = {
            "id": "att_123",
            "file_url": "https://files.monzo.com/file/abc123.jpg",
            "file_type": "image/jpeg",
            "created": "2023-01-01T00:00:00Z",
            "external_id": "ext-uuid",
            "transaction_id": "tx_123"
        }
        responses.add(
            responses.POST,
            "https://api.monzo.com/attachment/register",
            json=mock_response,
            status=200,
        )
        client = MonzoClient(access_token="test_token")
        result = client.register_attachment(
            file_url="https://files.monzo.com/file/abc123.jpg",
            external_id="ext-uuid",
            file_type="image/jpeg",
            transaction_id="tx_123"
        )
        assert result["id"] == mock_response["id"]
        assert result["file_url"] == mock_response["file_url"]
        assert result["transaction_id"] == mock_response["transaction_id"]

    @responses.activate
    def test_detach_attachment_success(self):
        """Test successful detach_attachment."""
        responses.add(
            responses.DELETE,
            "https://api.monzo.com/attachment/detach",
            json={},
            status=200,
        )
        client = MonzoClient(access_token="test_token")
        # Should not raise
        client.detach_attachment(attachment_id="att_123")
        # Check that the request was made with correct data
        req = responses.calls[0].request
        body = req.body.decode() if isinstance(req.body, bytes) else req.body
        assert body is not None
        assert "att_123" in body or "id" in body

    @responses.activate
    def test_add_transaction_receipt_success(self):
        """Test successful add_transaction_receipt."""
        mock_response = {
            "transaction_id": "tx_123",
            "receipt": {"items": [{"description": "Coffee", "amount": 300}]}
        }
        responses.add(
            responses.PUT,
            "https://api.monzo.com/transaction-receipts",
            json=mock_response,
            status=200,
        )
        client = MonzoClient(access_token="test_token")
        receipt = {"items": [{"description": "Coffee", "amount": 300}]}
        result = client.add_transaction_receipt("tx_123", receipt)
        assert result["transaction_id"] == "tx_123"
        assert result["receipt"] == receipt
