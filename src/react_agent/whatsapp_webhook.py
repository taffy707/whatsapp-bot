"""WhatsApp webhook server for receiving and processing messages."""

import os
import sys
from typing import Any, Dict, Optional, cast

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from react_agent import graph
from react_agent.context import Context
from react_agent.whatsapp_client import WhatsAppClient

# WhatsApp messages and agent replies routinely contain non-ASCII text (emoji,
# the °C degree symbol, etc.). On Windows the console defaults to cp1252, so a
# bare print() of such text raises UnicodeEncodeError and would abort the whole
# webhook handler before a reply is sent. Force UTF-8 on the log streams.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        _reconfigure(encoding="utf-8")

# Load environment variables from .env file
load_dotenv()


class WebhookMessage(BaseModel):
    """Model for incoming WhatsApp webhook messages."""

    object: str
    entry: list[Dict[str, Any]]


app = FastAPI(title="WhatsApp LangGraph Agent")

# Initialize WhatsApp client (will be created on first use)
whatsapp_client: Optional[WhatsAppClient] = None


def get_whatsapp_client() -> WhatsAppClient:
    """Get or create WhatsApp client instance."""
    global whatsapp_client
    if whatsapp_client is None:
        whatsapp_client = WhatsAppClient()
    return whatsapp_client


# Verification token for webhook setup
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "your_verify_token_here")


@app.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    """Verify webhook endpoint for WhatsApp setup.

    Meta will call this endpoint during webhook configuration with verification parameters.

    Args:
        request: FastAPI request object.

    Returns:
        Challenge string if verification succeeds, error otherwise.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        print("Webhook verified successfully!")
        return Response(content=challenge, media_type="text/plain")
    else:
        print("Webhook verification failed!")
        return Response(content="Verification failed", status_code=403)


@app.post("/webhook")
async def receive_message(webhook_data: WebhookMessage) -> Dict[str, str]:
    """Receive and process incoming WhatsApp messages.

    This endpoint receives webhook notifications from WhatsApp Business API,
    processes messages through the LangGraph agent, and sends responses back.

    Args:
        webhook_data: Webhook payload from WhatsApp.

    Returns:
        Success status dictionary.
    """
    try:
        # Extract message data from webhook
        for entry in webhook_data.entry:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])

                for message in messages:
                    # Extract message details
                    message_id = message.get("id")
                    from_number = message.get("from")
                    message_type = message.get("type")

                    # Only process text messages
                    if message_type == "text":
                        text_body = message.get("text", {}).get("body", "")

                        print(f"Received message from {from_number}: {text_body}")

                        # Get WhatsApp client instance
                        client = get_whatsapp_client()

                        # Mark message as read
                        await client.mark_message_as_read(message_id)

                        # Process message through LangGraph agent
                        # Use phone number as thread_id for conversation memory
                        agent_response = await process_with_agent(
                            text_body, thread_id=from_number
                        )

                        # Send response back to WhatsApp
                        await client.send_message(
                            to=from_number,
                            message=agent_response,
                        )

                        print(f"Sent response to {from_number}: {agent_response}")

        return {"status": "success"}

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        return {"status": "error", "message": str(e)}


async def process_with_agent(user_message: str, thread_id: str) -> str:
    """Process user message through the LangGraph agent.

    Args:
        user_message: The user's text message.
        thread_id: Unique identifier for the conversation thread (e.g., phone number).

    Returns:
        The agent's response as a string.
    """
    try:
        # Create context for the agent
        context = Context()

        # Invoke the agent with the user's message
        # thread_id enables conversation memory - same thread_id = same conversation
        result = await graph.ainvoke(
            cast(Any, {"messages": [("user", user_message)]}),
            context=context,
            config={"configurable": {"thread_id": thread_id}},
        )

        # Extract the last message from the agent's response
        last_message = result["messages"][-1]

        # Get text content from the message
        if hasattr(last_message, "content"):
            response_text = last_message.content
            if isinstance(response_text, str):
                return response_text
            elif isinstance(response_text, list):
                # Handle multipart content
                text_parts = []
                for part in response_text:
                    if isinstance(part, str):
                        text_parts.append(part)
                    elif isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                return " ".join(text_parts)

        return "I'm sorry, I couldn't process your request."

    except Exception as e:
        print(f"Error processing message with agent: {str(e)}")
        return f"An error occurred while processing your message: {str(e)}"


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint.

    Returns:
        Status dictionary.
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
