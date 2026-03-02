"""Data models for Monzo API responses using Pydantic."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MonzoBaseModel(BaseModel):
    """Base model for Monzo objects with common configuration."""
    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",  # Ignore extra fields from the API for stability
    )


class Account(MonzoBaseModel):
    """Represents a Monzo account."""
    id: str
    name: Optional[str] = None
    currency: str
    balance: int = 0  # Amount in minor units (pence)
    type: str
    description: Optional[str] = None
    created: Optional[datetime] = None
    closed: bool = False


class Balance(MonzoBaseModel):
    """Represents an account balance."""
    balance: int  # Amount in minor units (pence)
    currency: str
    spend_today: int  # Amount spent today in minor units
    local_currency: Optional[str] = None
    local_exchange_rate: Optional[float] = None
    local_spend: Optional[List[Dict[str, Any]]] = None


class Transaction(MonzoBaseModel):
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


class Pot(MonzoBaseModel):
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


class Webhook(MonzoBaseModel):
    """Represents a Monzo webhook."""
    id: str
    account_id: str
    url: str
    webhook_type: Optional[str] = Field(None, alias="type")
    created: Optional[datetime] = None


class FeedItem(MonzoBaseModel):
    """Represents a Monzo feed item."""
    id: str
    account_id: str
    title: str
    body: str
    image_url: Optional[str] = None
    action_url: Optional[str] = None
    created: Optional[datetime] = None


class Attachment(MonzoBaseModel):
    """Represents an attachment registered to a transaction."""
    id: str
    file_url: str
    file_type: str
    created: Optional[datetime] = None
    external_id: Optional[str] = None
    transaction_id: Optional[str] = None


class TransactionReceipt(MonzoBaseModel):
    """Represents a receipt attached to a transaction."""
    transaction_id: str
    receipt: Dict[str, Any]
