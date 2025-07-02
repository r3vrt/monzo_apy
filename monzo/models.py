"""Data models for Monzo API responses."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Account:
    """Represents a Monzo account."""

    id: str
    name: Optional[str]
    currency: str
    balance: int  # Amount in minor units (pence)
    type: str
    description: Optional[str] = None
    created: Optional[datetime] = None
    closed: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Account":
        """Create an Account instance from API response data.

        Args:
            data: Dictionary containing account data

        Returns:
            Account instance
        """
        return cls(
            id=data["id"],
            name=data.get("name"),
            currency=data["currency"],
            balance=data.get("balance", 0),
            type=data["type"],
            description=data.get("description"),
            created=(
                datetime.fromisoformat(data["created"]) if data.get("created") else None
            ),
            closed=data.get("closed", False),
        )


@dataclass
class Balance:
    """Represents an account balance."""

    balance: int  # Amount in minor units (pence)
    currency: str
    spend_today: int  # Amount spent today in minor units
    local_currency: Optional[str] = None
    local_exchange_rate: Optional[float] = None
    local_spend: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Balance":
        """Create a Balance instance from API response data.

        Args:
            data: Dictionary containing balance data

        Returns:
            Balance instance
        """
        return cls(
            balance=data["balance"],
            currency=data["currency"],
            spend_today=data["spend_today"],
            local_currency=data.get("local_currency"),
            local_exchange_rate=data.get("local_exchange_rate"),
            local_spend=data.get("local_spend"),
        )


@dataclass
class Transaction:
    """Represents a Monzo transaction."""

    id: str
    amount: int  # Amount in minor units (pence)
    currency: str
    description: str
    category: str
    merchant: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    created: Optional[datetime] = None
    settled: Optional[datetime] = None
    account_balance: Optional[int] = None
    local_amount: Optional[int] = None
    local_currency: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    international: Optional[Dict[str, Any]] = None
    top_up: Optional[bool] = None
    hide_amount: Optional[bool] = None
    can_add_to_tab: Optional[bool] = None
    can_be_excluded_from_breakdown: Optional[bool] = None
    can_be_made_subscription: Optional[bool] = None
    can_split_the_bill: Optional[bool] = None
    amount_is_pending: Optional[bool] = None
    atm_fees_detailed: Optional[Dict[str, Any]] = None
    parent_account_id: Optional[str] = None
    scheme: Optional[str] = None
    dedupe_id: Optional[str] = None
    originator: Optional[bool] = None
    include_in_spending: Optional[bool] = None
    can_watermark: Optional[bool] = None
    is_load: Optional[bool] = None
    settled_amount: Optional[int] = None
    settled_currency: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        """Create a Transaction instance from API response data.

        Args:
            data: Dictionary containing transaction data

        Returns:
            Transaction instance
        """
        return cls(
            id=data["id"],
            amount=data["amount"],
            currency=data["currency"],
            description=data["description"],
            category=data["category"],
            merchant=data.get("merchant"),
            notes=data.get("notes"),
            created=(
                datetime.fromisoformat(data["created"]) if data.get("created") else None
            ),
            settled=(
                datetime.fromisoformat(data["settled"]) if data.get("settled") else None
            ),
            account_balance=data.get("account_balance"),
            local_amount=data.get("local_amount"),
            local_currency=data.get("local_currency"),
            metadata=data.get("metadata"),
            attachments=data.get("attachments"),
            international=data.get("international"),
            top_up=data.get("top_up"),
            hide_amount=data.get("hide_amount"),
            can_add_to_tab=data.get("can_add_to_tab"),
            can_be_excluded_from_breakdown=data.get("can_be_excluded_from_breakdown"),
            can_be_made_subscription=data.get("can_be_made_subscription"),
            can_split_the_bill=data.get("can_split_the_bill"),
            amount_is_pending=data.get("amount_is_pending"),
            atm_fees_detailed=data.get("atm_fees_detailed"),
            parent_account_id=data.get("parent_account_id"),
            scheme=data.get("scheme"),
            dedupe_id=data.get("dedupe_id"),
            originator=data.get("originator"),
            include_in_spending=data.get("include_in_spending"),
            can_watermark=data.get("can_watermark"),
            is_load=data.get("is_load"),
            settled_amount=data.get("settled_amount"),
            settled_currency=data.get("settled_currency"),
        )


@dataclass
class Pot:
    """Represents a Monzo pot (savings goal)."""

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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pot":
        """Create a Pot instance from API response data.

        Args:
            data: Dictionary containing pot data

        Returns:
            Pot instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            balance=data["balance"],
            currency=data["currency"],
            style=data["style"],
            deleted=data.get("deleted", False),
            created=(
                datetime.fromisoformat(data["created"]) if data.get("created") else None
            ),
            updated=(
                datetime.fromisoformat(data["updated"]) if data.get("updated") else None
            ),
            goal_amount=data.get("goal_amount"),
            isa_wrapper=data.get("isa_wrapper"),
        )


@dataclass
class Webhook:
    """Represents a Monzo webhook."""

    id: str
    account_id: str
    url: str
    webhook_type: Optional[str] = None
    created: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Webhook":
        """Create a Webhook instance from API response data.

        Args:
            data: Dictionary containing webhook data

        Returns:
            Webhook instance
        """
        return cls(
            id=data["id"],
            account_id=data["account_id"],
            url=data["url"],
            webhook_type=data.get("type"),
            created=(
                datetime.fromisoformat(data["created"]) if data.get("created") else None
            ),
        )


@dataclass
class FeedItem:
    """Represents a Monzo feed item."""

    id: str
    account_id: str
    title: str
    body: str
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    created: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedItem":
        """Create a FeedItem instance from API response data.

        Args:
            data: Dictionary containing feed item data

        Returns:
            FeedItem instance
        """
        return cls(
            id=data["id"],
            account_id=data["account_id"],
            title=data["title"],
            body=data["body"],
            image_url=data.get("image_url"),
            action_url=data.get("action_url"),
            created=(
                datetime.fromisoformat(data["created"]) if data.get("created") else None
            ),
        )


@dataclass
class Attachment:
    """Represents an attachment registered to a transaction."""
    id: str
    file_url: str
    file_type: str
    created: Optional[datetime] = None
    external_id: Optional[str] = None
    transaction_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Attachment":
        return cls(
            id=data["id"],
            file_url=data["file_url"],
            file_type=data["file_type"],
            created=datetime.fromisoformat(data["created"]) if data.get("created") else None,
            external_id=data.get("external_id"),
            transaction_id=data.get("transaction_id"),
        )


@dataclass
class TransactionReceipt:
    """Represents a receipt attached to a transaction."""
    transaction_id: str
    receipt: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransactionReceipt":
        return cls(
            transaction_id=data["transaction_id"],
            receipt=data["receipt"],
        )
