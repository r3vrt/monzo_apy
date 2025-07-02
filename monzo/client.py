"""Main client for interacting with the Monzo API."""

import os
import uuid
import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlencode

import requests

from .exceptions import (
    MonzoAPIError,
    MonzoAuthenticationError,
    MonzoRateLimitError,
    MonzoValidationError,
)
from .models import Account, Balance, Pot, Transaction, Webhook, FeedItem


class MonzoClient:
    """Client for interacting with the Monzo API."""

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
    ):
        """Initialize the Monzo client.

        Args:
            access_token: Monzo API access token.
            refresh_token: Monzo API refresh token.
            client_id: OAuth client ID (required for OAuth flow)
            client_secret: OAuth client secret (required for OAuth flow)
            redirect_uri: Redirect URI for OAuth flow
            auth_file: Optional path to a JSON file to load/save auth info (default: config/auth.json)
            max_retries: Maximum number of retries for failed requests
            retry_delay: Base delay between retries (will be exponential)
            auto_save: Whether to automatically save auth info after token refresh (default: True)
        """
        if not auth_file:
            auth_file = os.path.join("config", "auth.json")
        
        # Initialize with passed parameters first
        self.access_token = access_token or os.getenv("MONZO_ACCESS_TOKEN")
        self.refresh_token = refresh_token or os.getenv("MONZO_REFRESH_TOKEN")
        self.client_id = client_id or os.getenv("MONZO_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("MONZO_CLIENT_SECRET")
        self.redirect_uri = redirect_uri or os.getenv("MONZO_REDIRECT_URI")
        
        # Only load from auth file if no tokens were provided and auth file exists
        if not self.access_token and os.path.exists(auth_file):
            self.load_auth(auth_file)

        self.session = requests.Session()
        if self.access_token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                }
            )
        else:
            self.session.headers.update({"Content-Type": "application/json"})
        self._auth_file = auth_file
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.auto_save = auto_save

    def save_auth(self, filename: Optional[str] = None) -> None:
        """Save current auth info to a JSON file in config/ directory by default."""
        filename = filename or self._auth_file or os.path.join("config", "auth.json")
        config_dir = os.path.dirname(filename)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
        }
        with open(filename, "w") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def load_auth(self, filename: str) -> None:
        """Load auth info from a JSON file and update the client."""
        with open(filename, "r") as f:
            data = json.load(f)
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        self.client_id = data.get("client_id")
        self.client_secret = data.get("client_secret")
        self.redirect_uri = data.get("redirect_uri")
        self._auth_file = filename
        if hasattr(self, "session"):
            self.session.headers["Authorization"] = f"Bearer {self.access_token}"

    def get_authorization_url(self, state: Optional[str] = None, scope: str = "openid email accounts") -> str:
        """Generate the Monzo OAuth2 authorization URL for user login/consent.

        Args:
            state: Optional CSRF token (random string)
            scope: OAuth scopes (default: openid email accounts)

        Returns:
            The URL to redirect the user to for authorization
        """
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

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange an authorization code for an access token and refresh token.

        Args:
            code: The authorization code returned by Monzo

        Returns:
            Token response dict (access_token, refresh_token, etc.)
        """
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("client_id, client_secret, and redirect_uri are required for token exchange")
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        response = requests.post(self.TOKEN_URL, data=data, timeout=30)
        response.raise_for_status()
        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token")
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        if self.auto_save:
            self.save_auth()  # Automatically save updated tokens
        return tokens

    def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh the access token using the refresh token.

        Returns:
            Token response dict (access_token, refresh_token, etc.)
        """
        if not self.client_id or not self.client_secret or not self.refresh_token:
            raise ValueError("client_id, client_secret, and refresh_token are required for token refresh")
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }
        response = requests.post(self.TOKEN_URL, data=data, timeout=30)
        response.raise_for_status()
        tokens = response.json()
        self.access_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token")
        self.session.headers["Authorization"] = f"Bearer {self.access_token}"
        if self.auto_save:
            self.save_auth()  # Automatically save updated tokens
        return tokens

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the Monzo API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/accounts")
            params: Query parameters
            data: Request body data

        Returns:
            API response data

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
            MonzoRateLimitError: If rate limit is exceeded
            MonzoValidationError: If request validation fails
        """
        return self._make_request_with_retry(method, endpoint, params, data)

    def _make_request_with_retry(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to the Monzo API with retry logic and exponential backoff.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/accounts")
            params: Query parameters
            data: Request body data

        Returns:
            API response data

        Raises:
            MonzoAPIError: If the API request fails after all retries
            MonzoAuthenticationError: If authentication fails
            MonzoRateLimitError: If rate limit is exceeded
            MonzoValidationError: If request validation fails
        """
        if not self.access_token:
            raise MonzoAuthenticationError("No access token provided")
        
        url = urljoin(self.BASE_URL, endpoint)
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                # Use form data for PUT requests and for POST to /webhooks or /feed
                if (
                    (method == "PUT" and data) or
                    (method == "POST" and data and endpoint in ["/webhooks", "/feed"])
                ):
                    # Convert values to strings for form data
                    form_data = {k: str(v) if not isinstance(v, dict) else json.dumps(v) for k, v in data.items()}
                    print(f"[DEBUG] {method} {endpoint} form_data: {form_data}")
                    response = self.session.request(
                        method=method,
                        url=url,
                        params=params,
                        data=form_data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        timeout=30,
                    )
                else:
                    response = self.session.request(
                        method=method,
                        url=url,
                        params=params,
                        json=data,
                        timeout=30,
                    )
                
                response.raise_for_status()
                
                # Handle empty responses (common with DELETE requests)
                if not response.content:
                    return {}
                    
                return response.json()

            except requests.exceptions.HTTPError as e:
                last_exception = e
                if response.status_code == 401:
                    raise MonzoAuthenticationError(
                        "Invalid access token", response_data=response.json()
                    )
                elif response.status_code == 429:
                    # Rate limit exceeded - wait and retry
                    if attempt < self.max_retries:
                        wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                        time.sleep(wait_time)
                        continue
                    else:
                        raise MonzoRateLimitError(
                            "Rate limit exceeded", response_data=response.json()
                        )
                elif response.status_code == 400:
                    error_data = response.json()
                    print(f"400 Error Response: {error_data}")
                    raise MonzoValidationError(
                        "Invalid request", response_data=error_data
                    )
                elif response.status_code >= 500:
                    # Server error - retry
                    if attempt < self.max_retries:
                        wait_time = self.retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                        continue
                    else:
                        raise MonzoAPIError(
                            f"API request failed: {response.status_code}",
                            status_code=response.status_code,
                            response_data=response.json() if response.content else {},
                        )
                else:
                    raise MonzoAPIError(
                        f"API request failed: {response.status_code}",
                        status_code=response.status_code,
                        response_data=response.json() if response.content else {},
                    )
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                last_exception = e
                if attempt < self.max_retries:
                    wait_time = self.retry_delay * (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                else:
                    raise MonzoAPIError(f"Request failed after {self.max_retries} retries: {e}")
            except requests.exceptions.RequestException as e:
                raise MonzoAPIError(f"Request failed: {e}")

        # This should never be reached, but just in case
        raise MonzoAPIError(f"Request failed after {self.max_retries} retries")

    def get_accounts(self) -> List[Account]:
        """Get all accounts for the authenticated user, returning all that are not closed."""
        response = self._make_request("GET", "/accounts")
        accounts = response["accounts"]
        filtered = [
            account for account in accounts
            if not account.get("closed", False)
        ]
        return [Account.from_dict(account) for account in filtered]

    def get_account(self, account_id: str) -> Account:
        """Get a specific account by ID.

        Args:
            account_id: The account ID

        Returns:
            Account instance

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        response = self._make_request("GET", f"/accounts/{account_id}")
        return Account.from_dict(response["account"])

    def get_balance(self, account_id: str) -> Balance:
        """Get the balance for a specific account.

        Args:
            account_id: The account ID

        Returns:
            Balance instance

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        response = self._make_request(
            "GET", "/balance", params={"account_id": account_id}
        )
        return Balance.from_dict(response)

    def get_transactions(
        self,
        account_id: str,
        limit: Optional[int] = None,
        since: Optional[str] = None,
        before: Optional[str] = None,
        auto_paginate: bool = False,
        ensure_recent_auth: bool = False,
    ) -> List[Transaction]:
        """Get transactions for a specific account.

        Args:
            account_id: The account ID
            limit: Maximum number of transactions to return per request
            since: ISO 8601 timestamp to get transactions since
            before: ISO 8601 timestamp to get transactions before
            auto_paginate: If True, automatically fetch all transactions using pagination
            ensure_recent_auth: If True, perform full reauthentication to ensure recent authentication
                              (required for access beyond 90 days of transactions)

        Returns:
            List of transactions

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
            ValueError: If full reauthentication is required but OAuth2 credentials are not configured

        Note:
            Monzo API limits transaction access to the last 90 days if the user
            authenticated more than 5 minutes ago. Set ensure_recent_auth=True
            to perform full reauthentication and access complete transaction history.
            This requires OAuth2 credentials (client_id, client_secret, redirect_uri).
        """
        if ensure_recent_auth:
            self.ensure_recent_authentication()
            
        if auto_paginate:
            return self._get_all_transactions(account_id, since, before)
        
        params = {"account_id": account_id}
        if limit:
            params["limit"] = str(limit)
        if since:
            params["since"] = since
        if before:
            params["before"] = before

        response = self._make_request("GET", "/transactions", params=params)
        return [Transaction.from_dict(tx) for tx in response["transactions"]]

    def _get_all_transactions(self, account_id: str, since: Optional[str] = None, before: Optional[str] = None) -> List[Transaction]:
        """Get all transactions using pagination.

        Args:
            account_id: The account ID
            since: ISO 8601 timestamp to get transactions since
            before: ISO 8601 timestamp to get transactions before

        Returns:
            List of all transactions
        """
        all_transactions = []
        before_id = before
        
        while True:
            params = {"account_id": account_id, "limit": "100"}
            if since:
                params["since"] = since
            if before_id:
                params["before"] = before_id

            response = self._make_request("GET", "/transactions", params=params)
            transactions = [Transaction.from_dict(tx) for tx in response["transactions"]]
            
            if not transactions:
                break
                
            all_transactions.extend(transactions)
            
            # Check if we have more transactions to fetch
            if len(transactions) < 100:
                break
                
            # Use the last transaction's ID as the 'before' parameter for next request
            before_id = transactions[-1].id
        
        return all_transactions

    def get_transaction(self, transaction_id: str) -> Transaction:
        """Get a specific transaction by ID.

        Args:
            transaction_id: The transaction ID

        Returns:
            Transaction instance

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        response = self._make_request("GET", f"/transactions/{transaction_id}")
        return Transaction.from_dict(response["transaction"])

    def annotate_transaction(
        self, transaction_id: str, metadata: Dict[str, str]
    ) -> Transaction:
        """Annotate a transaction with metadata.

        Args:
            transaction_id: The transaction ID
            metadata: Dictionary of metadata key-value pairs

        Returns:
            Updated Transaction instance

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        response = self._make_request(
            "PATCH", f"/transactions/{transaction_id}", data={"metadata": metadata}
        )
        return Transaction.from_dict(response["transaction"])

    def get_pots(self, account_id: str, pot_name: Optional[str] = None) -> List[Pot]:
        """Get all pots for the authenticated user for a specific account.

        Args:
            account_id: The account ID to filter pots (required)
            pot_name: Optional pot name to search for (case-insensitive partial match)

        Returns:
            List of user's pots, optionally filtered by name

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        params = {"current_account_id": account_id}
        response = self._make_request("GET", "/pots", params=params)
        pots = [Pot.from_dict(pot) for pot in response["pots"]]
        
        # Filter by pot name if provided
        if pot_name:
            pot_name_lower = pot_name.lower()
            pots = [pot for pot in pots if pot.name and pot_name_lower in pot.name.lower()]
        
        return pots

    def get_pot(self, pot_id: str) -> Pot:
        """Get a specific pot by ID.

        Args:
            pot_id: The pot ID

        Returns:
            Pot instance

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        response = self._make_request("GET", f"/pots/{pot_id}")
        return Pot.from_dict(response["pot"])

    def get_pot_by_name(self, account_id: str, pot_name: str) -> Pot:
        """Get a specific pot by name for a given account.

        Args:
            account_id: The account ID to search pots in
            pot_name: The pot name to search for (case-insensitive exact match)

        Returns:
            Pot instance

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
            ValueError: If no pot with the given name is found
        """
        pots = self.get_pots(account_id, pot_name=pot_name)
        
        # Find exact match (case-insensitive)
        pot_name_lower = pot_name.lower()
        for pot in pots:
            if pot.name and pot.name.lower() == pot_name_lower:
                return pot
        
        # If no exact match found, raise an error
        raise ValueError(f"No pot found with name '{pot_name}' in account {account_id}")

    def deposit_to_pot(
        self, pot_id: str, account_id: str, amount: int, dedupe_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Deposit money into a pot.

        Args:
            pot_id: The pot ID
            account_id: The account ID to withdraw from
            amount: Amount in minor units (pence)
            dedupe_id: Optional deduplication ID

        Returns:
            API response data

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        data = {
            "source_account_id": account_id,
            "amount": amount,
        }
        if dedupe_id:
            data["dedupe_id"] = dedupe_id

        return self._make_request("PUT", f"/pots/{pot_id}/deposit", data=data)

    def withdraw_from_pot(
        self, pot_id: str, account_id: str, amount: int, dedupe_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Withdraw money from a pot.

        Args:
            pot_id: The pot ID
            account_id: The account ID to deposit to
            amount: Amount in minor units (pence)
            dedupe_id: Optional deduplication ID

        Returns:
            API response data

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        data = {
            "destination_account_id": account_id,
            "amount": amount,
        }
        if dedupe_id:
            data["dedupe_id"] = dedupe_id

        return self._make_request("PUT", f"/pots/{pot_id}/withdraw", data=data)

    def whoami(self) -> Dict[str, Any]:
        """Get information about the authenticated user.

        Returns:
            User information

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        return self._make_request("GET", "/ping/whoami")

    def create_webhook(self, account_id: str, url: str) -> Webhook:
        """Create a webhook for real-time updates.

        Args:
            account_id: The account ID to monitor
            url: The URL to send webhook notifications to

        Returns:
            Webhook instance

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        data = {
            "account_id": account_id,
            "url": url,
        }
        response = self._make_request("POST", "/webhooks", data=data)
        return Webhook.from_dict(response["webhook"])

    def list_webhooks(self, account_id: str) -> List[Webhook]:
        """List all webhooks for the authenticated user for a specific account.

        Args:
            account_id: The account ID to list webhooks for

        Returns:
            List of webhook instances

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        params = {"account_id": account_id}
        response = self._make_request("GET", "/webhooks", params=params)
        return [Webhook.from_dict(webhook) for webhook in response["webhooks"]]

    def delete_webhook(self, webhook_id: str) -> None:
        """Delete a webhook.

        Args:
            webhook_id: The webhook ID to delete

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        self._make_request("DELETE", f"/webhooks/{webhook_id}")

    def create_feed_item(self, account_id: str, title: str, body: str, 
                        image_url: Optional[str] = None, 
                        action_url: Optional[str] = None) -> FeedItem:
        """Add a custom item to the Monzo feed.

        Args:
            account_id: The account ID to add the feed item to
            title: The title of the feed item
            body: The body text of the feed item
            image_url: Optional URL to an image to display
            action_url: Optional URL to open when the item is tapped

        Returns:
            FeedItem instance

        Raises:
            MonzoAPIError: If the API request fails
            MonzoAuthenticationError: If authentication fails
        """
        data = {
            "account_id": account_id,
            "type": "basic",
            "params[title]": title,
            "params[body]": body,
        }
        if image_url:
            data["params[image_url]"] = image_url
        if action_url:
            data["params[action_url]"] = action_url

        response = self._make_request("POST", "/feed", data=data)
        # The API doesn't return a feed_item object, but the creation was successful
        # We'll create a minimal FeedItem with the data we sent
        return FeedItem(
            id="created",  # Placeholder since API doesn't return an ID
            account_id=account_id,
            title=title,
            body=body,
            image_url=image_url,
            action_url=action_url,
        )

    def ensure_recent_authentication(self) -> None:
        """Ensure recent authentication for accessing complete transaction history.
        
        This method performs a full reauthentication (like a new user) to ensure
        the user can access transaction data beyond the 90-day limit imposed by 
        Monzo API.
        
        Note:
            Monzo API only allows access to the last 90 days of transactions
            if the user authenticated more than 5 minutes ago. This method
            performs a complete OAuth2 flow to enable access to complete 
            transaction history.
            
        Raises:
            ValueError: If client_id, client_secret, or redirect_uri are not configured
        """
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError(
                "client_id, client_secret, and redirect_uri are required for full reauthentication. "
                "Please configure these values and use the OAuth2 flow to get fresh tokens."
            )
        
        # For full reauthentication, we need to guide the user through the OAuth2 flow
        # This cannot be done automatically as it requires user interaction
        auth_url = self.get_authorization_url()
        raise ValueError(
            f"Full reauthentication required. Please visit this URL to reauthorize: {auth_url}\n"
            "After authorization, use exchange_code_for_token() with the returned code."
        )

    def perform_full_reauthentication(self, auth_code: str) -> Dict[str, Any]:
        """Perform full reauthentication using an authorization code.
        
        This method exchanges an authorization code for fresh tokens, performing
        a complete reauthentication that allows access to all transaction data.
        
        Args:
            auth_code: The authorization code from the OAuth2 flow
            
        Returns:
            Token response dict (access_token, refresh_token, etc.)
            
        Note:
            This method should be used after getting an authorization code from
            the OAuth2 flow initiated by ensure_recent_authentication().
        """
        return self.exchange_code_for_token(auth_code)

    def is_authentication_recent(self, max_age_minutes: int = 5) -> bool:
        """Check if the current authentication is recent enough for full transaction access.
        
        Args:
            max_age_minutes: Maximum age of authentication in minutes (default: 5)
            
        Returns:
            True if authentication is recent enough, False otherwise
            
        Note:
            This method provides a best-effort check. The actual limit is enforced
            by the Monzo API server-side. For guaranteed access to complete
            transaction history, use ensure_recent_authentication().
        """
        # Since we don't store token creation time, we can't determine exact age
        # This is a placeholder for future enhancement when token metadata is available
        # For now, always return False to encourage explicit token refresh
        return False

    def upload_attachment(self, file_type: str) -> Dict[str, Any]:
        """Get a pre-signed upload URL for an attachment.

        Args:
            file_type: The MIME type of the file (e.g., 'image/jpeg')

        Returns:
            Dict with 'upload_url' and 'file_url'
        """
        data = {"file_type": file_type}
        response = self._make_request("POST", "/attachment/upload", data=data)
        return response

    def register_attachment(self, file_url: str, external_id: str, file_type: str, transaction_id: str) -> Dict[str, Any]:
        """Register an uploaded file as an attachment to a transaction.

        Args:
            file_url: The URL of the uploaded file
            external_id: A unique ID for this attachment (e.g., UUID)
            file_type: The MIME type of the file
            transaction_id: The transaction to attach to

        Returns:
            Attachment info dict
        """
        data = {
            "file_url": file_url,
            "external_id": external_id,
            "file_type": file_type,
            "transaction_id": transaction_id,
        }
        response = self._make_request("POST", "/attachment/register", data=data)
        return response

    def detach_attachment(self, attachment_id: str) -> None:
        """Detach an attachment from a transaction.

        Args:
            attachment_id: The ID of the attachment to detach
        """
        data = {"id": attachment_id}
        self._make_request("DELETE", "/attachment/detach", data=data)

    def add_transaction_receipt(self, transaction_id: str, receipt: dict) -> Dict[str, Any]:
        """Add a receipt to a transaction.

        Args:
            transaction_id: The transaction ID
            receipt: The receipt data (must follow Monzo's schema)

        Returns:
            The API response dict
        """
        data = {"transaction_id": transaction_id, "receipt": receipt}
        response = self._make_request("PUT", "/transaction-receipts", data=data)
        return response
