"""WhatsApp Business API client for sending messages."""

import os
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel


class WhatsAppMessage(BaseModel):
    """WhatsApp message model."""

    messaging_product: str = "whatsapp"
    recipient_type: str = "individual"
    to: str
    type: str = "text"
    text: Dict[str, str]


class WhatsAppClient:
    """Client for interacting with WhatsApp Business API."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        business_account_id: Optional[str] = None,
    ):
        """Initialize WhatsApp client.

        Args:
            access_token: WhatsApp Business API access token.
            phone_number_id: WhatsApp Business phone number ID.
            business_account_id: WhatsApp Business Account ID (WABA ID).
        """
        self.access_token = access_token or os.getenv("WHATSAPP_ACCESS_TOKEN")
        self.phone_number_id = phone_number_id or os.getenv(
            "WHATSAPP_PHONE_NUMBER_ID"
        )
        self.business_account_id = business_account_id or os.getenv(
            "WHATSAPP_BUSINESS_ACCOUNT_ID"
        )
        self.base_url = "https://graph.facebook.com/v21.0"

        if not self.access_token:
            raise ValueError("WhatsApp access token is required")
        if not self.phone_number_id:
            raise ValueError("WhatsApp phone number ID is required")
        if not self.business_account_id:
            raise ValueError("WhatsApp Business Account ID is required")

    async def send_message(self, to: str, message: str) -> Dict[str, Any]:
        """Send a text message via WhatsApp.

        Args:
            to: Recipient's phone number (with country code, no + or spaces).
            message: Text message to send.

        Returns:
            API response dictionary.

        Raises:
            httpx.HTTPError: If the request fails.
        """
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        whatsapp_message = WhatsAppMessage(
            to=to,
            text={"body": message},
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=whatsapp_message.model_dump(),
                timeout=30.0,
            )

            # Log response for debugging
            if response.status_code != 200:
                error_detail = response.text
                print(f"WhatsApp API Error ({response.status_code}): {error_detail}")

            response.raise_for_status()
            return response.json()

    async def mark_message_as_read(self, message_id: str) -> Dict[str, Any]:
        """Mark a message as read.

        Args:
            message_id: ID of the message to mark as read.

        Returns:
            API response dictionary.
        """
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()

    async def get_business_account_info(self) -> Dict[str, Any]:
        """Get WhatsApp Business Account information.

        Returns:
            API response dictionary with account details.
        """
        url = f"{self.base_url}/{self.business_account_id}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        params = {"fields": "id,name,timezone_id,message_template_namespace"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
