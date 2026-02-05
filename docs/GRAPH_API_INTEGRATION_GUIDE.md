# Microsoft Graph API Integration Guide for Python

This guide covers integrating Microsoft Graph API for email operations in Python, including reading, writing, and sending emails.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Authentication](#authentication)
4. [Graph API Client Setup](#graph-api-client-setup)
5. [Reading Emails](#reading-emails)
6. [Sending Emails](#sending-emails)
7. [Working with Conversations](#working-with-conversations)
8. [Creating Draft Emails](#creating-draft-emails)
9. [Replying to Emails](#replying-to-emails)
10. [Data Models](#data-models)
11. [Replacing the Mock Provider](#replacing-the-mock-provider)
12. [Error Handling](#error-handling)
13. [Best Practices](#best-practices)
14. [Complete Example](#complete-example)

---

## Prerequisites

Before integrating Graph API:

1. Complete the [Azure Setup Guide](./AZURE_SETUP_GUIDE.md)
2. Have your credentials ready:
   - Tenant ID
   - Client ID
   - Client Secret (or Certificate)
3. Python 3.10+

---

## Installation

### Required Packages

```bash
# Using pip
pip install azure-identity msgraph-sdk httpx

# Using uv (recommended for this project)
uv add azure-identity msgraph-sdk httpx
```

### Package Descriptions

| Package | Purpose |
|---------|---------|
| `azure-identity` | Azure AD authentication |
| `msgraph-sdk` | Official Microsoft Graph SDK for Python |
| `httpx` | Async HTTP client (used by msgraph-sdk) |

### Alternative: Direct REST API

If you prefer not to use the SDK, you can use `httpx` or `aiohttp` directly:

```bash
pip install httpx aiohttp
```

---

## Authentication

### Client Credentials Flow (Application Permissions)

For daemon/service applications without user interaction:

```python
"""Authentication using client credentials (application permissions)."""

from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient

def get_graph_client() -> GraphServiceClient:
    """Create an authenticated Graph client using client credentials."""
    
    credential = ClientSecretCredential(
        tenant_id="YOUR_TENANT_ID",
        client_id="YOUR_CLIENT_ID",
        client_secret="YOUR_CLIENT_SECRET",
    )
    
    # Define the scopes for application permissions
    scopes = ["https://graph.microsoft.com/.default"]
    
    # Create the Graph client
    client = GraphServiceClient(credentials=credential, scopes=scopes)
    
    return client
```

### Certificate-Based Authentication (Production)

```python
"""Authentication using certificate (recommended for production)."""

from azure.identity import CertificateCredential
from msgraph import GraphServiceClient

def get_graph_client_with_cert() -> GraphServiceClient:
    """Create Graph client using certificate authentication."""
    
    credential = CertificateCredential(
        tenant_id="YOUR_TENANT_ID",
        client_id="YOUR_CLIENT_ID",
        certificate_path="path/to/certificate.pem",
        # Or use certificate_data for in-memory certificate
    )
    
    scopes = ["https://graph.microsoft.com/.default"]
    client = GraphServiceClient(credentials=credential, scopes=scopes)
    
    return client
```

### Using Environment Variables

```python
"""Authentication using environment variables."""

import os
from azure.identity import ClientSecretCredential, EnvironmentCredential
from msgraph import GraphServiceClient

def get_graph_client_from_env() -> GraphServiceClient:
    """Create Graph client using environment variables."""
    
    # Option 1: Explicit environment variable reading
    credential = ClientSecretCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
    )
    
    # Option 2: EnvironmentCredential automatically reads:
    # AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
    # credential = EnvironmentCredential()
    
    scopes = ["https://graph.microsoft.com/.default"]
    return GraphServiceClient(credentials=credential, scopes=scopes)
```

---

## Graph API Client Setup

### Complete Client Module

```python
"""Microsoft Graph API client for email operations."""

import os
from typing import Optional

from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient


class GraphConfig:
    """Configuration for Graph API client."""
    
    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID")
        self.client_id = client_id or os.getenv("AZURE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("AZURE_CLIENT_SECRET")
        self.user_id = user_id or os.getenv("GRAPH_USER_ID")
        
        if not all([self.tenant_id, self.client_id, self.client_secret]):
            raise ValueError(
                "Missing required Azure credentials. "
                "Set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET."
            )


class GraphEmailClient:
    """Client for Microsoft Graph email operations."""
    
    def __init__(self, config: Optional[GraphConfig] = None):
        self.config = config or GraphConfig()
        self._client: Optional[GraphServiceClient] = None
    
    @property
    def client(self) -> GraphServiceClient:
        """Lazy initialization of Graph client."""
        if self._client is None:
            credential = ClientSecretCredential(
                tenant_id=self.config.tenant_id,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
            )
            self._client = GraphServiceClient(
                credentials=credential,
                scopes=["https://graph.microsoft.com/.default"],
            )
        return self._client
    
    @property
    def user_id(self) -> str:
        """Get the user/mailbox ID to operate on."""
        if not self.config.user_id:
            raise ValueError("GRAPH_USER_ID not configured")
        return self.config.user_id
```

---

## Reading Emails

### List Messages

```python
"""Read emails from a mailbox."""

from msgraph.generated.users.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)


async def list_messages(
    client: GraphEmailClient,
    top: int = 25,
    filter_unread: bool = False,
) -> list[dict]:
    """List messages from the mailbox.
    
    Args:
        client: GraphEmailClient instance
        top: Maximum number of messages to return
        filter_unread: If True, only return unread messages
    
    Returns:
        List of message dictionaries
    """
    # Build query parameters
    query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        top=top,
        select=["id", "conversationId", "subject", "from", "toRecipients", 
                "receivedDateTime", "body", "bodyPreview", "isRead"],
        orderby=["receivedDateTime DESC"],
    )
    
    if filter_unread:
        query_params.filter = "isRead eq false"
    
    config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
        query_parameters=query_params,
    )
    
    # Make the request
    messages = await client.client.users.by_user_id(
        client.user_id
    ).messages.get(request_configuration=config)
    
    return [msg.__dict__ for msg in (messages.value or [])]
```

### Get Single Message

```python
async def get_message(client: GraphEmailClient, message_id: str) -> dict | None:
    """Get a single message by ID.
    
    Args:
        client: GraphEmailClient instance
        message_id: The message ID
    
    Returns:
        Message dictionary or None if not found
    """
    try:
        message = await client.client.users.by_user_id(
            client.user_id
        ).messages.by_message_id(message_id).get()
        
        return message.__dict__ if message else None
    except Exception as e:
        print(f"Error fetching message {message_id}: {e}")
        return None
```

### Get Messages by Conversation

```python
async def get_conversation_messages(
    client: GraphEmailClient,
    conversation_id: str,
) -> list[dict]:
    """Get all messages in a conversation thread.
    
    Args:
        client: GraphEmailClient instance
        conversation_id: The conversation ID
    
    Returns:
        List of messages in the conversation, sorted by date
    """
    from msgraph.generated.users.item.messages.messages_request_builder import (
        MessagesRequestBuilder,
    )
    
    query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        filter=f"conversationId eq '{conversation_id}'",
        orderby=["receivedDateTime ASC"],
        select=["id", "conversationId", "internetMessageId", "subject", 
                "from", "toRecipients", "receivedDateTime", "body", "bodyPreview"],
    )
    
    config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
        query_parameters=query_params,
    )
    
    messages = await client.client.users.by_user_id(
        client.user_id
    ).messages.get(request_configuration=config)
    
    return [msg.__dict__ for msg in (messages.value or [])]
```

---

## Sending Emails

### Send a New Email

```python
"""Send emails using Microsoft Graph API."""

from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
    SendMailPostRequestBody,
)
from msgraph.generated.models.message import Message
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.email_address import EmailAddress


async def send_email(
    client: GraphEmailClient,
    to_address: str,
    subject: str,
    body: str,
    content_type: str = "text",
    save_to_sent: bool = True,
) -> None:
    """Send a new email.
    
    Args:
        client: GraphEmailClient instance
        to_address: Recipient email address
        subject: Email subject
        body: Email body content
        content_type: "text" or "html"
        save_to_sent: Whether to save to Sent Items folder
    """
    # Create the message
    message = Message(
        subject=subject,
        body=ItemBody(
            content_type=BodyType.Html if content_type == "html" else BodyType.Text,
            content=body,
        ),
        to_recipients=[
            Recipient(
                email_address=EmailAddress(address=to_address),
            ),
        ],
    )
    
    # Create the request body
    request_body = SendMailPostRequestBody(
        message=message,
        save_to_sent_items=save_to_sent,
    )
    
    # Send the email
    await client.client.users.by_user_id(
        client.user_id
    ).send_mail.post(body=request_body)
    
    print(f"Email sent to {to_address}")
```

### Send Email with CC and BCC

```python
async def send_email_extended(
    client: GraphEmailClient,
    to_addresses: list[str],
    subject: str,
    body: str,
    cc_addresses: list[str] | None = None,
    bcc_addresses: list[str] | None = None,
    content_type: str = "text",
    importance: str = "normal",
) -> None:
    """Send email with extended options.
    
    Args:
        client: GraphEmailClient instance
        to_addresses: List of recipient addresses
        subject: Email subject
        body: Email body
        cc_addresses: Optional CC recipients
        bcc_addresses: Optional BCC recipients
        content_type: "text" or "html"
        importance: "low", "normal", or "high"
    """
    from msgraph.generated.models.importance import Importance
    
    # Map importance
    importance_map = {
        "low": Importance.Low,
        "normal": Importance.Normal,
        "high": Importance.High,
    }
    
    # Build recipients
    to_recipients = [
        Recipient(email_address=EmailAddress(address=addr))
        for addr in to_addresses
    ]
    
    cc_recipients = [
        Recipient(email_address=EmailAddress(address=addr))
        for addr in (cc_addresses or [])
    ]
    
    bcc_recipients = [
        Recipient(email_address=EmailAddress(address=addr))
        for addr in (bcc_addresses or [])
    ]
    
    message = Message(
        subject=subject,
        body=ItemBody(
            content_type=BodyType.Html if content_type == "html" else BodyType.Text,
            content=body,
        ),
        to_recipients=to_recipients,
        cc_recipients=cc_recipients if cc_recipients else None,
        bcc_recipients=bcc_recipients if bcc_recipients else None,
        importance=importance_map.get(importance, Importance.Normal),
    )
    
    request_body = SendMailPostRequestBody(
        message=message,
        save_to_sent_items=True,
    )
    
    await client.client.users.by_user_id(
        client.user_id
    ).send_mail.post(body=request_body)
```

---

## Working with Conversations

### List Conversations

```python
async def list_conversations(client: GraphEmailClient) -> list[dict]:
    """List unique conversations with latest message info.
    
    Returns:
        List of conversation summaries
    """
    from msgraph.generated.users.item.messages.messages_request_builder import (
        MessagesRequestBuilder,
    )
    
    # Get messages grouped by conversation
    query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        top=100,
        select=["id", "conversationId", "subject", "from", "receivedDateTime"],
        orderby=["receivedDateTime DESC"],
    )
    
    config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
        query_parameters=query_params,
    )
    
    messages = await client.client.users.by_user_id(
        client.user_id
    ).messages.get(request_configuration=config)
    
    # Group by conversationId
    conversations: dict[str, list] = {}
    for msg in (messages.value or []):
        conv_id = msg.conversation_id or msg.id
        if conv_id not in conversations:
            conversations[conv_id] = []
        conversations[conv_id].append(msg)
    
    # Build summary for each conversation
    result = []
    for conv_id, msgs in conversations.items():
        latest = msgs[0]  # Already sorted DESC
        sender = ""
        if latest.from_ and latest.from_.email_address:
            sender = latest.from_.email_address.address or ""
        
        result.append({
            "conversation_id": conv_id,
            "subject": latest.subject or "",
            "sender": sender,
            "latest_message_id": latest.id,
            "message_count": len(msgs),
            "latest_received": str(latest.received_date_time),
        })
    
    return result
```

---

## Creating Draft Emails

### Create a Draft

```python
async def create_draft(
    client: GraphEmailClient,
    to_address: str,
    subject: str,
    body: str,
    content_type: str = "text",
) -> str:
    """Create a draft email.
    
    Args:
        client: GraphEmailClient instance
        to_address: Recipient address
        subject: Email subject
        body: Email body
        content_type: "text" or "html"
    
    Returns:
        The draft message ID
    """
    message = Message(
        subject=subject,
        body=ItemBody(
            content_type=BodyType.Html if content_type == "html" else BodyType.Text,
            content=body,
        ),
        to_recipients=[
            Recipient(email_address=EmailAddress(address=to_address)),
        ],
    )
    
    # Create the draft (POST to /messages without sending)
    draft = await client.client.users.by_user_id(
        client.user_id
    ).messages.post(body=message)
    
    print(f"Draft created with ID: {draft.id}")
    return draft.id
```

### Send a Draft

```python
async def send_draft(client: GraphEmailClient, message_id: str) -> None:
    """Send a previously created draft.
    
    Args:
        client: GraphEmailClient instance
        message_id: The draft message ID
    """
    await client.client.users.by_user_id(
        client.user_id
    ).messages.by_message_id(message_id).send.post()
    
    print(f"Draft {message_id} sent")
```

### Update a Draft

```python
async def update_draft(
    client: GraphEmailClient,
    message_id: str,
    subject: str | None = None,
    body: str | None = None,
) -> None:
    """Update an existing draft.
    
    Args:
        client: GraphEmailClient instance
        message_id: The draft message ID
        subject: New subject (optional)
        body: New body (optional)
    """
    update_message = Message()
    
    if subject:
        update_message.subject = subject
    
    if body:
        update_message.body = ItemBody(
            content_type=BodyType.Text,
            content=body,
        )
    
    await client.client.users.by_user_id(
        client.user_id
    ).messages.by_message_id(message_id).patch(body=update_message)
    
    print(f"Draft {message_id} updated")
```

---

## Replying to Emails

### Reply to a Message

```python
from msgraph.generated.users.item.messages.item.reply.reply_post_request_body import (
    ReplyPostRequestBody,
)


async def reply_to_message(
    client: GraphEmailClient,
    message_id: str,
    comment: str,
) -> None:
    """Reply to a specific message.
    
    This creates a reply in the same conversation thread.
    
    Args:
        client: GraphEmailClient instance
        message_id: ID of the message to reply to
        comment: The reply content
    """
    request_body = ReplyPostRequestBody(comment=comment)
    
    await client.client.users.by_user_id(
        client.user_id
    ).messages.by_message_id(message_id).reply.post(body=request_body)
    
    print(f"Replied to message {message_id}")
```

### Reply All

```python
from msgraph.generated.users.item.messages.item.reply_all.reply_all_post_request_body import (
    ReplyAllPostRequestBody,
)


async def reply_all_to_message(
    client: GraphEmailClient,
    message_id: str,
    comment: str,
) -> None:
    """Reply all to a message.
    
    Args:
        client: GraphEmailClient instance
        message_id: ID of the message to reply to
        comment: The reply content
    """
    request_body = ReplyAllPostRequestBody(comment=comment)
    
    await client.client.users.by_user_id(
        client.user_id
    ).messages.by_message_id(message_id).reply_all.post(body=request_body)
    
    print(f"Replied all to message {message_id}")
```

### Create Reply Draft (for editing before sending)

```python
from msgraph.generated.users.item.messages.item.create_reply.create_reply_post_request_body import (
    CreateReplyPostRequestBody,
)


async def create_reply_draft(
    client: GraphEmailClient,
    message_id: str,
) -> str:
    """Create a reply draft that can be edited before sending.
    
    Args:
        client: GraphEmailClient instance
        message_id: ID of the message to reply to
    
    Returns:
        The draft message ID
    """
    request_body = CreateReplyPostRequestBody()
    
    draft = await client.client.users.by_user_id(
        client.user_id
    ).messages.by_message_id(message_id).create_reply.post(body=request_body)
    
    print(f"Reply draft created: {draft.id}")
    return draft.id
```

---

## Data Models

### Graph API Message Structure

```python
"""Pydantic models matching Microsoft Graph API message resource."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EmailAddress(BaseModel):
    """Graph API emailAddress resource."""
    address: str
    name: Optional[str] = None


class Recipient(BaseModel):
    """Graph API recipient resource."""
    email_address: EmailAddress = Field(alias="emailAddress")
    
    class Config:
        populate_by_name = True


class ItemBody(BaseModel):
    """Graph API itemBody resource."""
    content_type: str = Field(default="text", alias="contentType")  # "text" | "html"
    content: str = ""
    
    class Config:
        populate_by_name = True


class GraphMessage(BaseModel):
    """Microsoft Graph API message resource."""
    
    id: str
    conversation_id: Optional[str] = Field(None, alias="conversationId")
    internet_message_id: Optional[str] = Field(None, alias="internetMessageId")
    received_date_time: Optional[datetime] = Field(None, alias="receivedDateTime")
    sent_date_time: Optional[datetime] = Field(None, alias="sentDateTime")
    subject: str = ""
    body: ItemBody = ItemBody()
    body_preview: Optional[str] = Field(None, alias="bodyPreview")
    from_: Optional[Recipient] = Field(None, alias="from")
    to_recipients: list[Recipient] = Field(default_factory=list, alias="toRecipients")
    cc_recipients: list[Recipient] = Field(default_factory=list, alias="ccRecipients")
    bcc_recipients: list[Recipient] = Field(default_factory=list, alias="bccRecipients")
    reply_to: list[Recipient] = Field(default_factory=list, alias="replyTo")
    is_draft: bool = Field(False, alias="isDraft")
    is_read: bool = Field(False, alias="isRead")
    importance: str = "normal"  # "low" | "normal" | "high"
    has_attachments: bool = Field(False, alias="hasAttachments")
    
    class Config:
        populate_by_name = True
        extra = "allow"
```

---

## Replacing the Mock Provider

### Create a Real Graph Provider

To replace `GraphMockProvider` with a real implementation:

```python
"""Real Microsoft Graph mail provider."""

from pathlib import Path
from typing import Optional

from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.models.message import Message as GraphSDKMessage
from msgraph.generated.models.item_body import ItemBody as GraphSDKItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient as GraphSDKRecipient
from msgraph.generated.models.email_address import EmailAddress as GraphSDKEmailAddress
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
    SendMailPostRequestBody,
)
from msgraph.generated.users.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)

from src.mail_provider.graph_models import GraphMessage, SendPayload, Recipient, EmailAddress, ItemBody
from src.mail_provider.protocol import MailProvider
from src.utils.logger import get_logger, log_agent_step


logger = get_logger("email_automation.graph_provider")


class GraphProvider:
    """Real Microsoft Graph API mail provider.
    
    Implements the same interface as GraphMockProvider for easy swapping.
    """
    
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        user_id: str,
    ):
        self._user_id = user_id
        
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        
        self._client = GraphServiceClient(
            credentials=credential,
            scopes=["https://graph.microsoft.com/.default"],
        )
        
        logger.info("graph_provider.init", user_id=user_id)
    
    def _convert_sdk_message(self, msg: GraphSDKMessage) -> GraphMessage:
        """Convert SDK message to our GraphMessage model."""
        from_recipient = None
        if msg.from_ and msg.from_.email_address:
            from_recipient = Recipient(
                emailAddress=EmailAddress(
                    address=msg.from_.email_address.address or "",
                    name=msg.from_.email_address.name,
                )
            )
        
        to_recipients = []
        for r in (msg.to_recipients or []):
            if r.email_address:
                to_recipients.append(Recipient(
                    emailAddress=EmailAddress(
                        address=r.email_address.address or "",
                        name=r.email_address.name,
                    )
                ))
        
        body = ItemBody()
        if msg.body:
            body = ItemBody(
                contentType="html" if msg.body.content_type == BodyType.Html else "text",
                content=msg.body.content or "",
            )
        
        return GraphMessage(
            id=msg.id or "",
            conversationId=msg.conversation_id,
            internetMessageId=msg.internet_message_id,
            receivedDateTime=str(msg.received_date_time) if msg.received_date_time else None,
            subject=msg.subject or "",
            body=body,
            bodyPreview=msg.body_preview,
            from_=from_recipient,
            toRecipients=to_recipients,
            isDraft=msg.is_draft or False,
        )
    
    async def get_message(self, message_id: str) -> GraphMessage | None:
        """Get a single message by ID."""
        try:
            msg = await self._client.users.by_user_id(
                self._user_id
            ).messages.by_message_id(message_id).get()
            
            if msg:
                logger.debug("graph_provider.get_message.hit", message_id=message_id)
                return self._convert_sdk_message(msg)
            
            logger.debug("graph_provider.get_message.miss", message_id=message_id)
            return None
        except Exception as e:
            logger.error("graph_provider.get_message.error", message_id=message_id, error=str(e))
            return None
    
    async def get_conversation(self, conversation_id: str) -> list[GraphMessage]:
        """Get all messages in a conversation."""
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            filter=f"conversationId eq '{conversation_id}'",
            orderby=["receivedDateTime ASC"],
        )
        
        config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=query_params,
        )
        
        try:
            result = await self._client.users.by_user_id(
                self._user_id
            ).messages.get(request_configuration=config)
            
            messages = [self._convert_sdk_message(m) for m in (result.value or [])]
            logger.debug(
                "graph_provider.get_conversation",
                conversation_id=conversation_id,
                count=len(messages),
            )
            return messages
        except Exception as e:
            logger.error(
                "graph_provider.get_conversation.error",
                conversation_id=conversation_id,
                error=str(e),
            )
            return []
    
    async def list_conversations(self) -> list[dict]:
        """List unique conversations."""
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            top=100,
            select=["id", "conversationId", "subject", "from", "receivedDateTime"],
            orderby=["receivedDateTime DESC"],
        )
        
        config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=query_params,
        )
        
        result = await self._client.users.by_user_id(
            self._user_id
        ).messages.get(request_configuration=config)
        
        # Group by conversation
        by_conv: dict[str, list] = {}
        for msg in (result.value or []):
            cid = msg.conversation_id or msg.id
            if cid not in by_conv:
                by_conv[cid] = []
            by_conv[cid].append(msg)
        
        conversations = []
        for cid, msgs in by_conv.items():
            latest = msgs[0]
            sender = ""
            if latest.from_ and latest.from_.email_address:
                sender = latest.from_.email_address.address or ""
            
            conversations.append({
                "conversation_id": cid,
                "subject": latest.subject or "",
                "sender": sender,
                "latest_message_id": latest.id,
                "message_count": len(msgs),
            })
        
        logger.info("graph_provider.list_conversations", count=len(conversations))
        return conversations
    
    async def send_message(self, payload: SendPayload) -> GraphMessage:
        """Send a message."""
        log_agent_step("GraphProvider", "Send message", {"to": payload.to, "subject": payload.subject})
        
        message = GraphSDKMessage(
            subject=payload.subject,
            body=GraphSDKItemBody(
                content_type=BodyType.Html if payload.contentType == "html" else BodyType.Text,
                content=payload.body,
            ),
            to_recipients=[
                GraphSDKRecipient(
                    email_address=GraphSDKEmailAddress(address=payload.to),
                ),
            ],
        )
        
        request_body = SendMailPostRequestBody(
            message=message,
            save_to_sent_items=True,
        )
        
        await self._client.users.by_user_id(
            self._user_id
        ).send_mail.post(body=request_body)
        
        # Return a mock response (send_mail doesn't return the sent message)
        from datetime import datetime, timezone
        sent_dt = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        return GraphMessage(
            id=f"sent_{id(payload)}",
            conversationId=payload.conversationId,
            receivedDateTime=sent_dt,
            subject=payload.subject,
            body=ItemBody(contentType=payload.contentType, content=payload.body),
            toRecipients=[Recipient(emailAddress=EmailAddress(address=payload.to))],
            isDraft=False,
        )
```

### Factory Function for Provider Selection

```python
"""Factory for creating mail providers."""

import os
from pathlib import Path

from src.mail_provider.graph_mock import GraphMockProvider
from src.mail_provider.protocol import MailProvider


def create_mail_provider() -> MailProvider:
    """Create the appropriate mail provider based on configuration.
    
    Returns GraphProvider if Azure credentials are set,
    otherwise returns GraphMockProvider.
    """
    use_real_graph = os.getenv("USE_REAL_GRAPH", "false").lower() == "true"
    
    if use_real_graph:
        from src.mail_provider.graph_real import GraphProvider
        
        return GraphProvider(
            tenant_id=os.environ["AZURE_TENANT_ID"],
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_secret=os.environ["AZURE_CLIENT_SECRET"],
            user_id=os.environ["GRAPH_USER_ID"],
        )
    else:
        return GraphMockProvider(
            inbox_path=Path("data/inbox.json"),
            sent_items_path=Path("output/sent_items.json"),
        )
```

---

## Error Handling

### Common Exceptions

```python
"""Error handling for Graph API operations."""

from msgraph.generated.models.o_data_errors.o_data_error import ODataError


async def safe_get_message(client: GraphEmailClient, message_id: str) -> dict | None:
    """Get message with proper error handling."""
    try:
        message = await client.client.users.by_user_id(
            client.user_id
        ).messages.by_message_id(message_id).get()
        
        return message.__dict__ if message else None
        
    except ODataError as e:
        error_code = e.error.code if e.error else "Unknown"
        error_message = e.error.message if e.error else str(e)
        
        if error_code == "ErrorItemNotFound":
            print(f"Message {message_id} not found")
            return None
        elif error_code == "ErrorAccessDenied":
            print(f"Access denied to message {message_id}")
            raise PermissionError(f"Access denied: {error_message}")
        else:
            print(f"Graph API error: {error_code} - {error_message}")
            raise
            
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
```

### Retry Logic

```python
"""Retry decorator for Graph API calls."""

import asyncio
from functools import wraps
from typing import Callable, TypeVar

T = TypeVar("T")


def retry_on_throttle(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator to retry on throttling (429) errors."""
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except ODataError as e:
                    if e.response_status_code == 429:
                        # Throttled - wait and retry
                        delay = base_delay * (2 ** attempt)
                        print(f"Throttled, retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        last_exception = e
                    else:
                        raise
            
            raise last_exception
        
        return wrapper
    return decorator


# Usage
@retry_on_throttle(max_retries=3)
async def send_email_with_retry(client, to, subject, body):
    await send_email(client, to, subject, body)
```

---

## Best Practices

### 1. Use Batch Requests for Multiple Operations

```python
"""Batch multiple Graph API requests."""

from msgraph.generated.models.batch_request_content import BatchRequestContent
from msgraph.generated.models.batch_request_step import BatchRequestStep


async def batch_get_messages(client: GraphEmailClient, message_ids: list[str]) -> list:
    """Get multiple messages in a single batch request."""
    
    # Note: Full batch implementation requires the batch endpoint
    # This is a simplified example
    
    tasks = [
        client.client.users.by_user_id(client.user_id)
        .messages.by_message_id(msg_id).get()
        for msg_id in message_ids
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return [r for r in results if not isinstance(r, Exception)]
```

### 2. Use Select to Minimize Data Transfer

```python
# Bad - fetches all properties
messages = await client.users.by_user_id(user_id).messages.get()

# Good - fetches only needed properties
query = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
    select=["id", "subject", "from", "receivedDateTime"],
)
config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
    query_parameters=query,
)
messages = await client.users.by_user_id(user_id).messages.get(
    request_configuration=config
)
```

### 3. Handle Pagination

```python
async def get_all_messages(client: GraphEmailClient) -> list:
    """Get all messages with pagination handling."""
    all_messages = []
    
    result = await client.client.users.by_user_id(
        client.user_id
    ).messages.get()
    
    while result:
        all_messages.extend(result.value or [])
        
        # Check for next page
        if result.odata_next_link:
            # The SDK handles pagination automatically with iterator
            result = await client.client.users.by_user_id(
                client.user_id
            ).messages.with_url(result.odata_next_link).get()
        else:
            break
    
    return all_messages
```

### 4. Log All Operations

```python
import structlog

logger = structlog.get_logger()

async def send_email_logged(client, to, subject, body):
    """Send email with comprehensive logging."""
    
    logger.info(
        "graph.send_email.start",
        to=to,
        subject=subject,
        body_length=len(body),
    )
    
    try:
        await send_email(client, to, subject, body)
        logger.info("graph.send_email.success", to=to)
    except Exception as e:
        logger.error("graph.send_email.error", to=to, error=str(e))
        raise
```

---

## Complete Example

### Full Working Example

```python
"""Complete example: Read inbox, process, and send reply."""

import asyncio
import os
from dotenv import load_dotenv

from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import (
    SendMailPostRequestBody,
)
from msgraph.generated.models.message import Message
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.email_address import EmailAddress


async def main():
    # Load environment variables
    load_dotenv()
    
    # Create credential
    credential = ClientSecretCredential(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
    )
    
    # Create client
    client = GraphServiceClient(
        credentials=credential,
        scopes=["https://graph.microsoft.com/.default"],
    )
    
    user_id = os.environ["GRAPH_USER_ID"]
    
    # 1. List unread messages
    print("Fetching unread messages...")
    
    query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
        top=10,
        filter="isRead eq false",
        select=["id", "subject", "from", "receivedDateTime", "bodyPreview"],
        orderby=["receivedDateTime DESC"],
    )
    
    config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
        query_parameters=query_params,
    )
    
    messages = await client.users.by_user_id(user_id).messages.get(
        request_configuration=config
    )
    
    if not messages.value:
        print("No unread messages found.")
        return
    
    print(f"Found {len(messages.value)} unread messages:\n")
    
    for i, msg in enumerate(messages.value, 1):
        sender = ""
        if msg.from_ and msg.from_.email_address:
            sender = msg.from_.email_address.address
        print(f"{i}. From: {sender}")
        print(f"   Subject: {msg.subject}")
        print(f"   Preview: {msg.body_preview[:50]}...")
        print()
    
    # 2. Get full content of first message
    first_msg_id = messages.value[0].id
    full_message = await client.users.by_user_id(user_id).messages.by_message_id(
        first_msg_id
    ).get()
    
    print(f"Full message body:\n{full_message.body.content}\n")
    
    # 3. Send a reply (example - commented out to prevent accidental sends)
    """
    reply_body = "Thank you for your email. We will review and respond shortly."
    
    message = Message(
        subject=f"Re: {full_message.subject}",
        body=ItemBody(
            content_type=BodyType.Text,
            content=reply_body,
        ),
        to_recipients=[
            Recipient(
                email_address=EmailAddress(
                    address=full_message.from_.email_address.address,
                ),
            ),
        ],
    )
    
    request_body = SendMailPostRequestBody(
        message=message,
        save_to_sent_items=True,
    )
    
    await client.users.by_user_id(user_id).send_mail.post(body=request_body)
    print("Reply sent successfully!")
    """
    
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Next Steps

1. Update your `.env` with real Azure credentials
2. Set `USE_REAL_GRAPH=true` to switch from mock to real provider
3. Test with a non-production mailbox first
4. Implement proper error handling and logging
5. Consider adding rate limiting for bulk operations

## References

- [Microsoft Graph API Documentation](https://docs.microsoft.com/en-us/graph/api/overview)
- [Microsoft Graph Python SDK](https://github.com/microsoftgraph/msgraph-sdk-python)
- [Azure Identity Library](https://docs.microsoft.com/en-us/python/api/overview/azure/identity-readme)
- [Mail API Reference](https://docs.microsoft.com/en-us/graph/api/resources/mail-api-overview)
