"""Main client for interacting with the Monzo API (Sync and Async)."""

import os
import uuid
import json
import time
import asyncio
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlencode

import requests
import httpx

from .exceptions import (
    MonzoAPIError,
    MonzoAuthenticationError,
    MonzoRateLimitError,
    MonzoValidationError,
)
from .models import Account, Balance, Pot, Transaction, Webhook, FeedItem
from .auth import AuthStorage, FileAuthStorage, MemoryAuthStorage, MonzoCredentials


class MonzoClientBase:
    """Base class for Monzo clients containing shared configuration and credentials."""

    BASE_URL = "https://api.monzo.com"
    AUTH_URL = "https://auth.monzo.com/"
    TOKEN_URL = "https://api.monzo.com/oauth2/token"

    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        auth_file: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        auto_save: bool = True,
        credentials: Optional[dict] = None,
        timeout: float = 30.0,
        auth_storage: Optional[AuthStorage] = None,
    ):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.auto_save = auto_save
        self.timeout = timeout

        # Initialize storage
        if auth_storage:
            self.auth_storage = auth_storage
        elif credentials is not None:
            self.auth_storage = MemoryAuthStorage(MonzoCredentials.model_validate(credentials))
        else:
            filename = auth_file or os.path.join("config", "auth.json")
            self.auth_storage = FileAuthStorage(filename=filename)

        # Load initial credentials from storage
        self._credentials = self.auth_storage.load()

        # Override with constructor parameters OR environment variables if storage is empty
        self._credentials.access_token = access_token or self._credentials.access_token or os.getenv("MONZO_ACCESS_TOKEN")
        self._credentials.refresh_token = refresh_token or self._credentials.refresh_token or os.getenv("MONZO_REFRESH_TOKEN")
        self._credentials.client_id = client_id or self._credentials.client_id or os.getenv("MONZO_CLIENT_ID")
        self._credentials.client_secret = client_secret or self._credentials.client_secret or os.getenv("MONZO_CLIENT_SECRET")
        self._credentials.redirect_uri = redirect_uri or self._credentials.redirect_uri or os.getenv("MONZO_REDIRECT_URI")

    @property
    def access_token(self) -> Optional[str]:
        return self._credentials.access_token

    @access_token.setter
    def access_token(self, value: Optional[str]):
        self._credentials.access_token = value

    @property
    def refresh_token(self) -> Optional[str]:
        return self._credentials.refresh_token

    @refresh_token.setter
    def refresh_token(self, value: Optional[str]):
        self._credentials.refresh_token = value

    @property
    def client_id(self) -> Optional[str]:
        return self._credentials.client_id

    @client_id.setter
    def client_id(self, value: Optional[str]):
        self._credentials.client_id = value

    @property
    def client_secret(self) -> Optional[str]:
        return self._credentials.client_secret

    @client_secret.setter
    def client_secret(self, value: Optional[str]):
        self._credentials.client_secret = value

    @property
    def redirect_uri(self) -> Optional[str]:
        return self._credentials.redirect_uri

    @redirect_uri.setter
    def redirect_uri(self, value: Optional[str]):
        self._credentials.redirect_uri = value

    def save_auth(self, filename: Optional[str] = None) -> None:
        """Save current credentials to storage."""
        if filename and isinstance(self.auth_storage, FileAuthStorage):
            self.auth_storage.filename = filename
        self.auth_storage.save(self._credentials)

    def load_auth(self, filename: Optional[str] = None) -> None:
        """Load credentials from storage."""
        if filename and isinstance(self.auth_storage, FileAuthStorage):
            self.auth_storage.filename = filename
        self._credentials = self.auth_storage.load()

    def get_authorization_url(self, state: Optional[str] = None, scope: str = "openid email accounts") -> str:
        """Generate the Monzo OAuth2 authorization URL."""
        if not self.client_id or not self.redirect_uri:
            raise ValueError("client_id and redirect_uri are required for OAuth flow")
        state = state or str(uuid.uuid4())
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": scope,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    def is_authentication_recent(self, max_age_minutes: int = 5) -> bool:
        """Check if the current authentication is recent enough (Placeholder)."""
        return False

    def ensure_recent_authentication(self) -> None:
        """Ensure recent authentication for accessing complete transaction history."""
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("client_id, client_secret, and redirect_uri are required for full reauthentication.")
        auth_url = self.get_authorization_url()
        raise ValueError(f"Full reauthentication required. Please visit this URL to reauthorize: {auth_url}")

    def _get_retry_after(self, response_headers: Any) -> float:
        """Parse the Retry-After header from the response."""
        retry_after = response_headers.get("Retry-After")
        if not retry_after:
            return 0.0
        try:
            return float(retry_after)
        except ValueError:
            # If it's an HTTP-date, we would need to parse it. 
            # Most modern APIs use seconds. 
            # We'll default to 0.0 if parsing fails to allow standard backoff.
            return 0.0


class MonzoClient(MonzoClientBase):
    """Synchronous client for interacting with the Monzo API using requests."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = requests.Session()
        self._update_session_headers()

    def _update_session_headers(self):
        if self.access_token:
            self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
        self.session.headers.update({"Content-Type": "application/json"})

    def load_auth(self, filename: Optional[str] = None) -> None:
        super().load_auth(filename)
        if hasattr(self, "session"):
            self._update_session_headers()

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange an authorization code for tokens."""
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("client_id, client_secret, and redirect_uri are required")
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        response = requests.post(self.TOKEN_URL, data=data, timeout=self.timeout)
        response.raise_for_status()
        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token")
        self._update_session_headers()
        if self.auto_save:
            self.save_auth()
        return tokens

    def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh the access token."""
        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise ValueError("client_id, client_secret, and refresh_token are required")
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }
        response = requests.post(self.TOKEN_URL, data=data, timeout=self.timeout)
        response.raise_for_status()
        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token")
        self._update_session_headers()
        if self.auto_save:
            self.save_auth()
        return tokens

    def perform_full_reauthentication(self, auth_code: str) -> Dict[str, Any]:
        """Perform full reauthentication using an authorization code."""
        return self.exchange_code_for_token(auth_code)

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.access_token:
            raise MonzoAuthenticationError("No access token provided")
        
        url = urljoin(self.BASE_URL, endpoint)
        
        for attempt in range(self.max_retries + 1):
            try:
                if (
                    (method in ["PUT", "POST", "PATCH", "DELETE"] and data) and 
                    (endpoint in ["/webhooks", "/feed", "/attachment/register", "/attachment/detach", "/transaction-receipts"] or endpoint.endswith("/deposit") or endpoint.endswith("/withdraw"))
                ):
                    form_data = {k: str(v) if not isinstance(v, dict) else json.dumps(v) for k, v in data.items()}
                    response = self.session.request(
                        method=method,
                        url=url,
                        params=params,
                        data=form_data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=self.timeout,
                    )
                else:
                    response = self.session.request(
                        method=method, url=url, params=params, json=data, timeout=self.timeout,
                    )
                
                response.raise_for_status()
                return response.json() if response.content else {}

            except requests.exceptions.HTTPError as e:
                if response.status_code == 401:
                    raise MonzoAuthenticationError("Invalid access token", response_data=response.json())
                elif response.status_code == 429:
                    if attempt < self.max_retries:
                        wait_time = self._get_retry_after(response.headers) or (self.retry_delay * (2 ** attempt))
                        time.sleep(wait_time)
                        continue
                    raise MonzoRateLimitError("Rate limit exceeded", response_data=response.json())
                elif response.status_code == 400:
                    raise MonzoValidationError("Invalid request", response_data=response.json())
                elif response.status_code >= 500:
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay * (2 ** attempt))
                        continue
                raise MonzoAPIError(f"API request failed: {response.status_code}", status_code=response.status_code, response_data=response.json() if response.content else {})
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay * (2 ** attempt))
                    continue
                raise MonzoAPIError(f"Request failed after {self.max_retries} retries: {e}")
        raise MonzoAPIError(f"Request failed after {self.max_retries} retries")

    def get_accounts(self) -> List[Account]:
        response = self._make_request("GET", "/accounts")
        filtered = [acc for acc in response["accounts"] if not acc.get("closed", False)]
        return [Account.model_validate(acc) for acc in filtered]

    def get_account(self, account_id: str) -> Account:
        response = self._make_request("GET", f"/accounts/{account_id}")
        return Account.model_validate(response["account"])

    def get_balance(self, account_id: str) -> Balance:
        response = self._make_request("GET", "/balance", params={"account_id": account_id})
        return Balance.model_validate(response)

    def get_transactions(self, account_id: str, since: Optional[str] = None, before: Optional[str] = None, ensure_recent_auth: bool = False) -> List[Transaction]:
        if ensure_recent_auth:
            self.ensure_recent_authentication()
        all_transactions = []
        current_since = since
        while True:
            params = {"account_id": account_id, "limit": "100"}
            if current_since: params["since"] = current_since
            if before: params["before"] = before

            response = self._make_request("GET", "/transactions", params=params)
            transactions = [Transaction.model_validate(tx) for tx in response["transactions"]]
            if not transactions: break
            all_transactions.extend(transactions)
            if len(transactions) < 100: break
            
            last_transaction = transactions[-1]
            from datetime import timedelta
            if last_transaction.created:
                current_since = (last_transaction.created + timedelta(seconds=1)).isoformat()
            else: break
        return all_transactions

    def get_transaction(self, transaction_id: str) -> Transaction:
        response = self._make_request("GET", f"/transactions/{transaction_id}")
        return Transaction.model_validate(response["transaction"])

    def annotate_transaction(self, transaction_id: str, metadata: Dict[str, str]) -> Transaction:
        response = self._make_request("PATCH", f"/transactions/{transaction_id}", data={"metadata": metadata})
        return Transaction.model_validate(response["transaction"])

    def get_pots(self, account_id: str, pot_name: Optional[str] = None) -> List[Pot]:
        response = self._make_request("GET", "/pots", params={"current_account_id": account_id})
        pots = [Pot.model_validate(pot) for pot in response["pots"]]
        if pot_name:
            pot_name_lower = pot_name.lower()
            pots = [p for p in pots if p.name and pot_name_lower in p.name.lower()]
        return pots

    def get_pot_by_name(self, account_id: str, pot_name: str) -> Pot:
        pots = self.get_pots(account_id, pot_name=pot_name)
        pot_name_lower = pot_name.lower()
        for pot in pots:
            if pot.name and pot.name.lower() == pot_name_lower:
                return pot
        raise ValueError(f"No pot found with name '{pot_name}'")

    def deposit_to_pot(self, pot_id: str, account_id: str, amount: int, dedupe_id: Optional[str] = None) -> Dict[str, Any]:
        data = {"source_account_id": account_id, "amount": amount}
        if dedupe_id: data["dedupe_id"] = dedupe_id
        return self._make_request("PUT", f"/pots/{pot_id}/deposit", data=data)

    def withdraw_from_pot(self, pot_id: str, account_id: str, amount: int, dedupe_id: Optional[str] = None) -> Dict[str, Any]:
        data = {"destination_account_id": account_id, "amount": amount}
        if dedupe_id: data["dedupe_id"] = dedupe_id
        return self._make_request("PUT", f"/pots/{pot_id}/withdraw", data=data)

    def whoami(self) -> Dict[str, Any]:
        return self._make_request("GET", "/ping/whoami")

    def create_webhook(self, account_id: str, url: str) -> Webhook:
        response = self._make_request("POST", "/webhooks", data={"account_id": account_id, "url": url})
        return Webhook.model_validate(response["webhook"])

    def list_webhooks(self, account_id: str) -> List[Webhook]:
        response = self._make_request("GET", "/webhooks", params={"account_id": account_id})
        return [Webhook.model_validate(webhook) for webhook in response["webhooks"]]

    def delete_webhook(self, webhook_id: str) -> None:
        self._make_request("DELETE", f"/webhooks/{webhook_id}")

    def create_feed_item(self, account_id: str, title: str, body: str, image_url: Optional[str] = None, action_url: Optional[str] = None) -> FeedItem:
        data = {"account_id": account_id, "type": "basic", "params[title]": title, "params[body]": body}
        if image_url: data["params[image_url]"] = image_url
        if action_url: data["params[action_url]"] = action_url
        self._make_request("POST", "/feed", data=data)
        return FeedItem(id="created", account_id=account_id, title=title, body=body, image_url=image_url, action_url=action_url)

    def upload_attachment(self, file_type: str) -> Dict[str, Any]:
        return self._make_request("POST", "/attachment/upload", data={"file_type": file_type})

    def register_attachment(self, file_url: str, external_id: str, file_type: str, transaction_id: str) -> Dict[str, Any]:
        data = {"file_url": file_url, "external_id": external_id, "file_type": file_type, "transaction_id": transaction_id}
        return self._make_request("POST", "/attachment/register", data=data)

    def detach_attachment(self, attachment_id: str) -> None:
        self._make_request("DELETE", "/attachment/detach", data={"id": attachment_id})

    def add_transaction_receipt(self, transaction_id: str, receipt: dict) -> Dict[str, Any]:
        data = {"transaction_id": transaction_id, "receipt": receipt}
        return self._make_request("PUT", "/transaction-receipts", data=data)


class AsyncMonzoClient(MonzoClientBase):
    """Asynchronous client for interacting with the Monzo API using httpx."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        self._update_headers()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _update_headers(self):
        if not self._client: return
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        self._client.headers.update(headers)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
            self._update_headers()
        return self._client

    def load_auth(self, filename: Optional[str] = None) -> None:
        super().load_auth(filename)
        self._update_headers()

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("client_id, client_secret, and redirect_uri are required")
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        client = await self._get_client()
        response = await client.post(self.TOKEN_URL, data=data)
        response.raise_for_status()
        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token")
        self._update_headers()
        if self.auto_save:
            self.save_auth()
        return tokens

    async def refresh_access_token(self) -> Dict[str, Any]:
        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise ValueError("client_id, client_secret, and refresh_token are required")
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }
        client = await self._get_client()
        response = await client.post(self.TOKEN_URL, data=data)
        response.raise_for_status()
        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token")
        self._update_headers()
        if self.auto_save:
            self.save_auth()
        return tokens

    async def perform_full_reauthentication(self, auth_code: str) -> Dict[str, Any]:
        return await self.exchange_code_for_token(auth_code)

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.access_token:
            raise MonzoAuthenticationError("No access token provided")
        
        url = urljoin(self.BASE_URL, endpoint)
        client = await self._get_client()

        for attempt in range(self.max_retries + 1):
            try:
                if (
                    (method in ["PUT", "POST", "PATCH", "DELETE"] and data) and 
                    (endpoint in ["/webhooks", "/feed", "/attachment/register", "/attachment/detach", "/transaction-receipts"] or endpoint.endswith("/deposit") or endpoint.endswith("/withdraw"))
                ):
                    form_data = {k: str(v) if not isinstance(v, dict) else json.dumps(v) for k, v in data.items()}
                    response = await client.request(
                        method=method,
                        url=url,
                        params=params,
                        data=form_data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                    )
                else:
                    response = await client.request(
                        method=method, url=url, params=params, json=data,
                    )
                
                response.raise_for_status()
                return response.json() if response.content else {}

            except httpx.HTTPStatusError as e:
                if response.status_code == 401:
                    raise MonzoAuthenticationError("Invalid access token", response_data=response.json())
                elif response.status_code == 429:
                    if attempt < self.max_retries:
                        wait_time = self._get_retry_after(response.headers) or (self.retry_delay * (2 ** attempt))
                        await asyncio.sleep(wait_time)
                        continue
                    raise MonzoRateLimitError("Rate limit exceeded", response_data=response.json())
                elif response.status_code == 400:
                    raise MonzoValidationError("Invalid request", response_data=response.json())
                elif response.status_code >= 500:
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delay * (2 ** attempt))
                        continue
                raise MonzoAPIError(f"API request failed: {response.status_code}", status_code=response.status_code, response_data=response.json() if response.content else {})
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                    continue
                raise MonzoAPIError(f"Request failed after {self.max_retries} retries: {e}")
        raise MonzoAPIError(f"Request failed after {self.max_retries} retries")

    async def get_accounts(self) -> List[Account]:
        response = await self._make_request("GET", "/accounts")
        filtered = [acc for acc in response["accounts"] if not acc.get("closed", False)]
        return [Account.model_validate(acc) for acc in filtered]

    async def get_account(self, account_id: str) -> Account:
        response = await self._make_request("GET", f"/accounts/{account_id}")
        return Account.model_validate(response["account"])

    async def get_balance(self, account_id: str) -> Balance:
        response = await self._make_request("GET", "/balance", params={"account_id": account_id})
        return Balance.model_validate(response)

    async def get_transactions(self, account_id: str, since: Optional[str] = None, before: Optional[str] = None, ensure_recent_auth: bool = False) -> List[Transaction]:
        if ensure_recent_auth:
            self.ensure_recent_authentication()
        all_transactions = []
        current_since = since
        while True:
            params = {"account_id": account_id, "limit": "100"}
            if current_since: params["since"] = current_since
            if before: params["before"] = before

            response = await self._make_request("GET", "/transactions", params=params)
            transactions = [Transaction.model_validate(tx) for tx in response["transactions"]]
            if not transactions: break
            all_transactions.extend(transactions)
            if len(transactions) < 100: break
            
            last_transaction = transactions[-1]
            from datetime import timedelta
            if last_transaction.created:
                current_since = (last_transaction.created + timedelta(seconds=1)).isoformat()
            else: break
        return all_transactions

    async def get_transaction(self, transaction_id: str) -> Transaction:
        response = await self._make_request("GET", f"/transactions/{transaction_id}")
        return Transaction.model_validate(response["transaction"])

    async def annotate_transaction(self, transaction_id: str, metadata: Dict[str, str]) -> Transaction:
        response = await self._make_request("PATCH", f"/transactions/{transaction_id}", data={"metadata": metadata})
        return Transaction.model_validate(response["transaction"])

    async def get_pots(self, account_id: str, pot_name: Optional[str] = None) -> List[Pot]:
        response = await self._make_request("GET", "/pots", params={"current_account_id": account_id})
        pots = [Pot.model_validate(pot) for pot in response["pots"]]
        if pot_name:
            pot_name_lower = pot_name.lower()
            pots = [p for p in pots if p.name and pot_name_lower in p.name.lower()]
        return pots

    async def get_pot_by_name(self, account_id: str, pot_name: str) -> Pot:
        pots = await self.get_pots(account_id, pot_name=pot_name)
        pot_name_lower = pot_name.lower()
        for pot in pots:
            if pot.name and pot.name.lower() == pot_name_lower:
                return pot
        raise ValueError(f"No pot found with name '{pot_name}'")

    async def deposit_to_pot(self, pot_id: str, account_id: str, amount: int, dedupe_id: Optional[str] = None) -> Dict[str, Any]:
        data = {"source_account_id": account_id, "amount": amount}
        if dedupe_id: data["dedupe_id"] = dedupe_id
        return await self._make_request("PUT", f"/pots/{pot_id}/deposit", data=data)

    async def withdraw_from_pot(self, pot_id: str, account_id: str, amount: int, dedupe_id: Optional[str] = None) -> Dict[str, Any]:
        data = {"destination_account_id": account_id, "amount": amount}
        if dedupe_id: data["dedupe_id"] = dedupe_id
        return await self._make_request("PUT", f"/pots/{pot_id}/withdraw", data=data)

    async def whoami(self) -> Dict[str, Any]:
        return await self._make_request("GET", "/ping/whoami")

    async def create_webhook(self, account_id: str, url: str) -> Webhook:
        response = await self._make_request("POST", "/webhooks", data={"account_id": account_id, "url": url})
        return Webhook.model_validate(response["webhook"])

    async def list_webhooks(self, account_id: str) -> List[Webhook]:
        response = await self._make_request("GET", "/webhooks", params={"account_id": account_id})
        return [Webhook.model_validate(webhook) for webhook in response["webhooks"]]

    async def delete_webhook(self, webhook_id: str) -> None:
        await self._make_request("DELETE", f"/webhooks/{webhook_id}")

    async def create_feed_item(self, account_id: str, title: str, body: str, image_url: Optional[str] = None, action_url: Optional[str] = None) -> FeedItem:
        data = {"account_id": account_id, "type": "basic", "params[title]": title, "params[body]": body}
        if image_url: data["params[image_url]"] = image_url
        if action_url: data["params[action_url]"] = action_url
        await self._make_request("POST", "/feed", data=data)
        return FeedItem(id="created", account_id=account_id, title=title, body=body, image_url=image_url, action_url=action_url)

    async def upload_attachment(self, file_type: str) -> Dict[str, Any]:
        return await self._make_request("POST", "/attachment/upload", data={"file_type": file_type})

    async def register_attachment(self, file_url: str, external_id: str, file_type: str, transaction_id: str) -> Dict[str, Any]:
        data = {"file_url": file_url, "external_id": external_id, "file_type": file_type, "transaction_id": transaction_id}
        return await self._make_request("POST", "/attachment/register", data=data)

    async def detach_attachment(self, attachment_id: str) -> None:
        await self._make_request("DELETE", "/attachment/detach", data={"id": attachment_id})

    async def add_transaction_receipt(self, transaction_id: str, receipt: dict) -> Dict[str, Any]:
        data = {"transaction_id": transaction_id, "receipt": receipt}
        return await self._make_request("PUT", "/transaction-receipts", data=data)
