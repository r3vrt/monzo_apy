# Monzo Python API Client

A comprehensive Python client for the Monzo API with OAuth2 authentication, token refresh, and robust error handling.

## What is Possible with the Monzo API?

This library implements all features that are possible with the [Monzo public API](https://docs.monzo.com/):

- **OAuth2 Authentication**: Full support for login, token refresh, and secure token storage
- **Account Info**: List your accounts, get account details
- **Balance**: Get the balance for your accounts
- **Transactions**: List, get, and annotate your own transactions (with auto-pagination)
- **Pots**: List, get, deposit to, and withdraw from your own pots
- **Webhooks**: Create, list, and delete webhooks for your own accounts
- **Feed Items**: Add custom feed items to your own account
- **Whoami**: Get info about the authenticated user
- **Error Handling**: Robust custom exceptions and retry logic
- **Rate Limiting**: Automatic handling with exponential backoff

**Limitations of the Monzo API:**
- You cannot send money to other users (only between your own accounts/pots)
- No API for creating or managing standing orders/direct debits
- No API for card management (freeze/unfreeze, etc.)
- No access to other users' data
- No sandbox/test environment (all API calls are live)
- Transaction history is limited to the last 90 days unless you re-authenticate within 5 minutes

For full details, see the [Monzo API documentation](https://docs.monzo.com/).

## Features

### Phase 1: Core API (Everything the Monzo API Publicly Supports)
- OAuth2 authentication (login, token refresh, save/load tokens)
- Get accounts (list, details)
- Get balance
- Get transactions (list, details, annotate, auto-pagination)
- Get pots (list, details, deposit, withdraw)
- Webhooks (create, list, delete)
- Feed items (add custom items)
- Whoami (get user info)
- Robust error handling (custom exceptions)
- Rate limiting and retry logic

### Phase 2: Developer Experience & Automation
- CLI tools for common flows (auth, account info, transactions)
- Automated OAuth2 flow (as you have now)
- Config file management (pretty-printed, secure)
- Integration tests (real API, with clear warnings)
- Mock-based unit tests (using responses)
- Documentation and usage examples

### Phase 3: Advanced Features & Helpers
- Auto-pagination for all list endpoints
- Helper methods for "recent authentication" (for full transaction history)
- Data model improvements (type hints, optional fields)
- More robust error reporting/logging
- Async support (future enhancement, not supported by Monzo API but can be added for client-side concurrency)

## Installation

```bash
pip install monzo-apy
```

## Quick Start

### 1. Set up OAuth2 credentials

First, create a Monzo developer account and get your OAuth2 credentials from the [Monzo Developer Portal](https://developers.monzo.com/).

**Quick Setup:**
1. Copy the sample configuration: `cp config/auth.example.json config/auth.json`
2. Edit `config/auth.json` with your credentials (or use the auth flow script)

### 2. Authentication Flow

The library provides a simple authentication script to guide you through the OAuth2 process:

```bash
python auth_flow.py
```

**Step-by-step process:**

1. **Run the auth flow script** - It will prompt for your OAuth2 credentials
2. **Visit the authorization URL** - The script will display a URL to visit in your browser
3. **⚠️ Approve in Monzo app** - After clicking the link, check your phone for a Monzo app notification
4. **Complete authorization** - Approve the request in your Monzo app
5. **Copy the redirect URL** - Copy the full URL you're redirected to (including the `?code=...` parameter)
6. **Paste the URL** - Paste it back into the terminal when prompted
7. **Tokens saved** - Your access and refresh tokens will be saved to `config/auth.json`

**Important Notes:**
- You must approve the authorization request in your Monzo app
- Authorization codes expire quickly (usually within 10 minutes)
- The script saves your credentials for future use

### 3. Basic usage

```python
from monzo import MonzoClient

# Initialize client with OAuth2 credentials
client = MonzoClient(
    client_id="your_client_id",
    client_secret="your_client_secret",
    redirect_uri="http://localhost/callback"
)

# Get authorization URL
auth_url = client.get_authorization_url()
print(f"Visit this URL to authorize: {auth_url}")

# ⚠️  IMPORTANT: After clicking the link, you may need to approve access in your Monzo app!
#    - Check your phone for a Monzo app notification
#    - Or open the Monzo app and look for a pending authorization request
#    - Approve the request to continue with the authentication flow

# After authorization, exchange code for tokens
code = "authorization_code_from_callback"
tokens = client.exchange_code_for_token(code)

# Save authentication info
client.save_auth()

# Now you can use the API
accounts = client.get_accounts()
for account in accounts:
    print(f"Account: {account.name} - Balance: {account.balance}")
```

### 4. Using saved authentication

```python
# Load saved authentication
client = MonzoClient(auth_file="config/auth.json")

# Get account information
accounts = client.get_accounts()
balance = client.get_balance(accounts[0].id)

# Get transactions with auto-pagination
transactions = client.get_transactions(accounts[0].id, auto_paginate=True)
```

## API Reference

### Authentication

#### `MonzoClient(auth_file=None, **kwargs)`
Initialize the Monzo client.

**Parameters:**
- `auth_file`: Path to JSON file containing auth info (default: `config/auth.json`)
- `access_token`: Direct access token
- `refresh_token`: Direct refresh token
- `client_id`: OAuth2 client ID
- `client_secret`: OAuth2 client secret
- `redirect_uri`: OAuth2 redirect URI
- `max_retries`: Maximum retries for failed requests (default: 3)
- `retry_delay`: Base delay between retries in seconds (default: 1.0)

#### `get_authorization_url(state=None, scope="openid email accounts")`
Get the OAuth2 authorization URL.

#### `exchange_code_for_token(code)`
Exchange authorization code for access and refresh tokens.

#### `refresh_access_token()`
Refresh the access token using the refresh token.

#### `save_auth(filename=None)`
Save authentication info to a JSON file.

#### `load_auth(filename)`
Load authentication info from a JSON file.

### Authentication Helpers

#### `ensure_recent_authentication()`
Ensure recent authentication for accessing complete transaction history.

This method performs a full reauthentication (like a new user) to ensure
the user can access transaction data beyond the 90-day limit imposed by 
Monzo API.

**Note:** Monzo API only allows access to the last 90 days of transactions
if the user authenticated more than 5 minutes ago. This method performs
a complete OAuth2 flow to enable access to complete transaction history.
Requires OAuth2 credentials (client_id, client_secret, redirect_uri).

#### `is_authentication_recent(max_age_minutes=5)`
Check if the current authentication is recent enough for full transaction access.

**Parameters:**
- `max_age_minutes`: Maximum age of authentication in minutes (default: 5)

**Returns:**
- True if authentication is recent enough, False otherwise

**Note:** This method provides a best-effort check. The actual limit is enforced
by the Monzo API server-side. For guaranteed access to complete transaction
history, use `ensure_recent_authentication()`.

### Account Management

#### `get_accounts()`
Get all accounts for the authenticated user (excludes closed accounts).

#### `get_account(account_id)`
Get a specific account by ID.

#### `get_balance(account_id)`
Get the balance for a specific account.

### Transaction Management

**⚠️ Important Limitation**: Monzo API only allows retrieval of the last 90 days of transactions if the user authenticated more than 5 minutes prior to the request. To access all transaction data, users need to perform a full reauthentication.

#### `get_transactions(account_id, limit=None, since=None, before=None, auto_paginate=False)`
Get transactions for a specific account.

**Parameters:**
- `account_id`: The account ID
- `limit`: Maximum number of transactions per request
- `since`: ISO 8601 timestamp to get transactions since
- `before`: ISO 8601 timestamp to get transactions before
- `auto_paginate`: If True, automatically fetch all transactions using pagination

**Authentication Requirements:**
- **Recent authentication (within 5 minutes)**: Can access all transaction data
- **Older authentication (>5 minutes)**: Limited to last 90 days of transactions
- **Full reauthentication needed**: To access complete transaction history beyond 90 days

**Example:**
```python
# For complete transaction history, ensure recent authentication
client.ensure_recent_authentication()  # This will guide you through OAuth2 flow
transactions = client.get_transactions(account_id, auto_paginate=True)

# For 90-day limit (older authentication)
transactions = client.get_transactions(account_id, limit=100)

# Get all transactions with auto-pagination (ensures recent authentication)
all_transactions = client.get_transactions(account_id, auto_paginate=True, ensure_recent_auth=True)
```

#### `get_transaction(transaction_id)`
Get a specific transaction by ID.

#### `annotate_transaction(transaction_id, metadata)`
Annotate a transaction with metadata.

### Pot Management

#### `get_pots(account_id, pot_name=None)`
Get all pots for a specific account, optionally filtered by name.

#### `get_pot(pot_id)`
Get a specific pot by ID.

#### `get_pot_by_name(account_id, pot_name)`
Get a specific pot by name (case-insensitive exact match).

#### `deposit_to_pot(pot_id, account_id, amount, dedupe_id=None)`
Deposit money into a pot.

#### `withdraw_from_pot(pot_id, account_id, amount, dedupe_id=None)`
Withdraw money from a pot.

### Webhook Management (Phase 1)

#### `create_webhook(account_id, url, webhook_type="transaction.created")`
Create a webhook for real-time updates.

#### `list_webhooks(account_id)`
List all webhooks for a specific account.

#### `delete_webhook(webhook_id)`
Delete a webhook.

### Feed Items (Phase 1)

#### `create_feed_item(account_id, title, body, image_url=None, action_url=None)`
Add a custom item to the Monzo feed.

### Rate Limiting & Retry Logic (Phase 1)

The client automatically handles rate limiting and transient failures with exponential backoff:

- **Automatic retries**: Up to 3 retries by default (configurable)
- **Exponential backoff**: Delay increases with each retry
- **Rate limit handling**: Respects 429 responses with appropriate delays
- **Server error recovery**: Retries on 5xx errors

## Data Models

### Account
```python
@dataclass
class Account:
    id: str
    name: Optional[str]
    currency: str
    balance: int  # Amount in minor units (pence)
    type: str
    description: Optional[str] = None
    created: Optional[datetime] = None
    closed: bool = False
```

### Balance
```python
@dataclass
class Balance:
    balance: int  # Amount in minor units (pence)
    currency: str
    spend_today: int  # Amount spent today in minor units
    local_currency: Optional[str] = None
    local_exchange_rate: Optional[float] = None
    local_spend: Optional[List[Dict[str, Any]]] = None
```

### Transaction
```python
@dataclass
class Transaction:
    id: str
    amount: int  # Amount in minor units (pence)
    currency: str
    description: str
    category: str
    merchant: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    created: Optional[datetime] = None
    settled: Optional[datetime] = None
    # ... additional fields
```

### Pot
```python
@dataclass
class Pot:
    id: str
    name: str
    balance: int  # Amount in minor units (pence)
    currency: str
    style: str
    deleted: bool = False
    created: Optional[datetime] = None
    updated: Optional[datetime] = None
    goal_amount: Optional[int] = None
    isa_wrapper: Optional[str] = None
```

### Webhook (Phase 1)
```python
@dataclass
class Webhook:
    id: str
    account_id: str
    url: str
    webhook_type: str
    created: Optional[datetime] = None
```

### FeedItem (Phase 1)
```python
@dataclass
class FeedItem:
    id: str
    account_id: str
    title: str
    body: str
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    created: Optional[datetime] = None
```

## Error Handling

The client provides comprehensive error handling with custom exceptions:

- `MonzoAuthenticationError`: Authentication failures
- `MonzoAPIError`: General API errors
- `MonzoRateLimitError`: Rate limit exceeded
- `MonzoValidationError`: Invalid request parameters

## Examples

### Complete OAuth2 Flow

```python
from monzo import MonzoClient

# Initialize client
client = MonzoClient(
    client_id="your_client_id",
    client_secret="your_client_secret",
    redirect_uri="http://localhost/callback"
)

# Step 1: Get authorization URL
auth_url = client.get_authorization_url()
print(f"Visit: {auth_url}")

# Step 2: After user authorizes, get the code from callback
code = "authorization_code_from_callback"

# Step 3: Exchange code for tokens
tokens = client.exchange_code_for_token(code)

# Step 4: Save for future use
client.save_auth()

# Step 5: Use the API
accounts = client.get_accounts()
for account in accounts:
    print(f"Account: {account.name}")
    balance = client.get_balance(account.id)
    print(f"Balance: £{balance.balance / 100:.2f}")
```

### Working with Transactions

```python
# Get recent transactions (90-day limit if authentication is older than 5 minutes)
transactions = client.get_transactions(account_id, limit=10)

# Get all transactions with auto-pagination (ensures recent authentication)
all_transactions = client.get_transactions(account_id, auto_paginate=True, ensure_recent_auth=True)

# Alternative: manually ensure recent authentication
client.ensure_recent_authentication()
all_transactions = client.get_transactions(account_id, auto_paginate=True)

# Get transactions since a specific date (requires recent authentication)
from datetime import datetime, timedelta
since_date = (datetime.now() - timedelta(days=365)).isoformat()
old_transactions = client.get_transactions(
    account_id, 
    since=since_date, 
    ensure_recent_auth=True
)

# Annotate a transaction
client.annotate_transaction(
    transaction_id="tx_123",
    metadata={"category": "groceries", "notes": "Weekly shop"}
)
```

### Pot Management

```python
# Get all pots
pots = client.get_pots(account_id)

# Find a specific pot by name
savings_pot = client.get_pot_by_name(account_id, "Savings")

# Deposit money
client.deposit_to_pot(savings_pot.id, account_id, 1000)  # £10.00

# Withdraw money
client.withdraw_from_pot(savings_pot.id, account_id, 500)  # £5.00
```

### Webhook Management (Phase 1)

```python
# Create a webhook
webhook = client.create_webhook(
    account_id="acc_123",
    url="https://your-server.com/webhook",
    webhook_type="transaction.created"
)

# List webhooks
webhooks = client.list_webhooks(account_id)

# Delete a webhook
client.delete_webhook(webhook.id)
```

### Feed Items (Phase 1)

```python
# Add a custom feed item
feed_item = client.create_feed_item(
    account_id="acc_123",
    title="Budget Alert",
    body="You've spent 80% of your monthly budget",
    image_url="https://example.com/alert-icon.png",
    action_url="https://example.com/budget-details"
)
```

## Testing

### Unit Tests
```bash
pytest tests/test_client.py
```

### Integration Tests
```bash
# Set up config/auth.json with your credentials first
pytest tests/integration/test_live_client.py -m integration
```

## Configuration

The client automatically manages authentication configuration in JSON format:

```json
{
    "access_token": "your_access_token",
    "refresh_token": "your_refresh_token", 
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "redirect_uri": "http://localhost/callback"
}
```

## Development

### Setup
```bash
git clone <repository>
cd monzo
pip install -e .
pip install -r requirements-dev.txt
```

### Code Quality
```bash
black monzo/ tests/
isort monzo/ tests/
flake8 monzo/ tests/
```

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## Roadmap

### Phase 1 ✅ (Completed)
- [x] Webhook management
- [x] Feed items
- [x] Auto-pagination for transactions
- [x] Rate limiting & retry logic

### Phase 2 (In Progress)
**Enhanced Transaction Features:**
- [ ] Transaction attachments (receipts, photos)
  - [ ] Upload attachment to transaction
  - [ ] List transaction attachments
  - [ ] Download attachment
  - [ ] Delete attachment
- [ ] Spending insights and categorization
  - [ ] Get merchant information
  - [ ] Transaction categorization
  - [ ] Spending patterns analysis
- [ ] Transaction search and filtering improvements
  - [ ] Advanced search by merchant, category, amount range
  - [ ] Date range filtering with timezone support
  - [ ] Transaction export (CSV, JSON)

**Card Management:**
- [ ] Get card information
  - [ ] List all cards for account
  - [ ] Get specific card details
  - [ ] Card spending limits and controls
- [ ] Card operations
  - [ ] Freeze/unfreeze cards
  - [ ] Card replacement
  - [ ] Update card settings

**Spending Analytics:**
- [ ] Spending patterns and trends
  - [ ] Monthly spending analysis
  - [ ] Category-based spending breakdown
  - [ ] Merchant spending analysis
- [ ] Budget tracking
  - [ ] Set budget limits by category
  - [ ] Track spending against budgets
  - [ ] Budget alerts and notifications
- [ ] Spending reports
  - [ ] Generate spending reports
  - [ ] Export analytics data
  - [ ] Custom date range reports

**Async Support:**
- [ ] Async/await versions of all client methods
  - [ ] Async client class (`AsyncMonzoClient`)
  - [ ] Convert all methods to async
  - [ ] Maintain backward compatibility
- [ ] Concurrent request handling
  - [ ] Batch operations
  - [ ] Parallel API calls
  - [ ] Connection pooling for async
- [ ] Background webhook processing
  - [ ] Async webhook handlers
  - [ ] Webhook signature verification
  - [ ] Webhook replay protection

### Phase 3 (Future)
**Webhook Signature Verification:**
- [ ] Verify webhook authenticity
  - [ ] Implement HMAC signature verification
  - [ ] Webhook replay protection
  - [ ] Secure webhook processing
- [ ] Webhook management improvements
  - [ ] Webhook health monitoring
  - [ ] Webhook retry logic
  - [ ] Webhook event filtering

**Bulk Operations:**
- [ ] Batch transaction operations
  - [ ] Bulk transaction annotation
  - [ ] Bulk transaction categorization
  - [ ] Bulk transaction export
- [ ] Bulk pot transfers
  - [ ] Multiple pot deposits/withdrawals
  - [ ] Scheduled pot transfers
  - [ ] Bulk pot management
- [ ] Mass operations
  - [ ] Bulk account operations
  - [ ] Bulk card operations
  - [ ] Bulk webhook management

**Advanced Error Handling:**
- [ ] Circuit breaker pattern
  - [ ] Implement circuit breaker for API calls
  - [ ] Configurable failure thresholds
  - [ ] Automatic recovery mechanisms
- [ ] Detailed error categorization
  - [ ] Enhanced exception hierarchy
  - [ ] Error context and debugging info
  - [ ] Error reporting and logging
- [ ] Error recovery strategies
  - [ ] Automatic retry with exponential backoff
  - [ ] Fallback mechanisms
  - [ ] Graceful degradation

**Performance Optimizations:**
- [ ] Connection pooling improvements
  - [ ] Optimize HTTP connection reuse
  - [ ] Connection pooling configuration
  - [ ] Connection health monitoring
- [ ] Caching strategies
  - [ ] Response caching for static data
  - [ ] Cache invalidation strategies
  - [ ] Configurable cache TTL
- [ ] Request batching
  - [ ] Batch API requests where possible
  - [ ] Reduce API call overhead
  - [ ] Optimize pagination
- [ ] Memory optimization
  - [ ] Streaming for large datasets
  - [ ] Memory-efficient data structures
  - [ ] Garbage collection optimization

**Additional Features:**
- [ ] Real-time transaction streaming
- [ ] Advanced authentication methods
- [ ] Multi-account support improvements
- [ ] International currency support
- [ ] Mobile app integration helpers
- [ ] Third-party service integrations 