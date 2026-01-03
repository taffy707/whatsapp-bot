# WhatsApp Agent Setup Guide

This guide will walk you through setting up a WhatsApp agent powered by your LangGraph ReAct agent.

## Overview

The WhatsApp integration allows users to interact with your LangGraph agent via WhatsApp messages. The system:

1. Receives messages from WhatsApp via webhook
2. Processes messages through the LangGraph ReAct agent
3. Sends the agent's response back to the user on WhatsApp

## Prerequisites

- A Facebook Business account
- A phone number for WhatsApp Business (can use Meta's test number initially)
- A publicly accessible URL for your webhook (use ngrok for local development)

## Part 1: Meta/Facebook Configuration

### Step 1: Create a Meta Business Portfolio

1. Navigate to [business.facebook.com](https://business.facebook.com)
2. Log in with your Facebook account
3. If you don't have a business portfolio:
   - Expand the left-hand menu
   - Click "Create business portfolio"
   - Follow the prompts to create your portfolio

### Step 2: Create a WhatsApp App

1. In Meta Business Suite, go to **Settings** (bottom left)
2. Under "Accounts," click **Apps**
3. Click **Add an app** → **Create a new app ID**
4. If prompted, confirm your account by adding a mobile number or credit card
5. Create the app:
   - Give it a name (e.g., "My WhatsApp Agent")
   - Select **Other** for use cases → Continue
   - Select **Business** as the app type (required for WhatsApp)
   - Confirm details and select your business portfolio
   - Click **Create app**

### Step 3: Get App Credentials

1. On the app dashboard, click **Setup** under WhatsApp
2. On the left sidebar, under "App settings," click **Basic**
3. Copy the following credentials:
   - **App ID** (this is your `WHATSAPP_APP_ID`)
   - **App Secret** (click "Show" to reveal, this is your `WHATSAPP_APP_SECRET`)

### Step 4: Get WhatsApp Access Token, Phone Number ID, and Business Account ID

1. In your app dashboard, on the left sidebar under WhatsApp, click **API Setup**
2. You'll see:
   - A test phone number provided by Facebook (or you can add your own business number)
   - Click **Generate access token**
3. Grant permissions:
   - Continue with your Facebook account
   - Opt into current and future WhatsApp accounts
   - Review permissions (manage WhatsApp accounts, access conversations)
   - Click **Save**
4. Copy the following credentials:

   **Access Token** (your `WHATSAPP_ACCESS_TOKEN`):
   - Found on the API Setup page after generating it
   - This is a long string starting with "EAA..."

   **Phone Number ID** (your `WHATSAPP_PHONE_NUMBER_ID`):
   - Found on the API Setup page, displayed below the phone number
   - It's a numeric ID (e.g., "102364578901234")

   **WhatsApp Business Account ID** (your `WHATSAPP_BUSINESS_ACCOUNT_ID`):
   - Also called WABA ID
   - **Method 1:** Look at the URL when you're on the WhatsApp API Setup page. It will contain `waba_id=XXXXX` - that's your Business Account ID
   - **Method 2:** On the API Setup page, it may be displayed as "WhatsApp Business Account ID" or "Business Account ID"
   - It's a numeric ID (e.g., "123456789012345")

**Important:** The access token shown is temporary (24 hours). For production, you'll need to generate a permanent access token through the System Users section in Meta Business Suite.

### Step 5: Add a Test Recipient (for testing)

1. On the same API Setup page, scroll to "To"
2. Enter your WhatsApp phone number with country code (e.g., 14155551234)
3. Click **Send test message** to verify it works
4. Check your WhatsApp for the test message

## Part 2: Local Setup

### Step 1: Install Dependencies

```bash
# Install all dependencies including FastAPI and uvicorn
uv pip install -r pyproject.toml
```

### Step 2: Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your credentials:
```bash
# WhatsApp Business API Configuration
WHATSAPP_ACCESS_TOKEN=your_access_token_here
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id_here
WHATSAPP_BUSINESS_ACCOUNT_ID=your_business_account_id_here
WHATSAPP_VERIFY_TOKEN=your_custom_verify_token_here
WHATSAPP_APP_ID=your_app_id_here
WHATSAPP_APP_SECRET=your_app_secret_here

# Required for the agent to work
ANTHROPIC_API_KEY=your_anthropic_key_here
# OR
OPENAI_API_KEY=your_openai_key_here

# Required for the search tool
TAVILY_API_KEY=your_tavily_key_here
```

**Important Notes:**

- **WHATSAPP_VERIFY_TOKEN**: This is a **custom string that YOU create** (not from Meta). Choose any secure, random string like `"my_secret_webhook_token_2024"`. You'll use this same string when configuring the webhook in Meta. Think of it as a password to verify that you own the webhook endpoint.

- **WHATSAPP_BUSINESS_ACCOUNT_ID**: This is the WABA ID from Meta (see Step 4 above for where to find it).

### Step 3: Expose Your Local Server (for development)

For local development, you need a public URL. Use ngrok:

```bash
# Install ngrok if you haven't already
brew install ngrok  # macOS
# or download from https://ngrok.com/download

# Start ngrok on port 8000
ngrok http 8000
```

Copy the HTTPS URL provided by ngrok (e.g., `https://abc123.ngrok.io`). You'll need this for webhook configuration.

### Step 4: Start the Webhook Server

```bash
# Start the FastAPI server
python -m uvicorn react_agent.whatsapp_webhook:app --host 0.0.0.0 --port 8000 --reload
```

The server will start on `http://localhost:8000`.

## Part 3: Configure WhatsApp Webhook

### Step 1: Add Webhook URL in Meta

1. Go back to your app in Meta Business Suite
2. On the left sidebar under WhatsApp, click **Configuration**
3. Find the "Webhook" section and click **Edit**
4. Enter your webhook details:
   - **Callback URL:** `https://your-ngrok-url.ngrok.io/webhook` (replace with your actual ngrok URL)
   - **Verify token:** The same value you set for `WHATSAPP_VERIFY_TOKEN` in your `.env` file
5. Click **Verify and save**

If successful, you'll see "Webhook verified successfully!" in your server logs.

### Step 2: Subscribe to Webhook Events

1. In the same Webhook section, click **Manage**
2. Subscribe to the following webhook fields:
   - **messages** (required to receive incoming messages)
3. Click **Subscribe**

## Part 4: Testing

### Test the Integration

1. Send a message to your WhatsApp Business number (the test number from Meta)
2. The webhook server should:
   - Receive the message
   - Process it through the LangGraph agent
   - Send the agent's response back to your WhatsApp

3. Check your server logs to see the message flow:
```
Received message from 14155551234: Hello!
Sent response to 14155551234: Hi! I'm a helpful AI assistant...
```

### Health Check

You can verify the server is running:
```bash
curl http://localhost:8000/health
```

Should return:
```json
{"status": "healthy"}
```

## Architecture

### Files Created

- **`src/react_agent/whatsapp_client.py`** - WhatsApp Business API client for sending messages
- **`src/react_agent/whatsapp_webhook.py`** - FastAPI webhook server for receiving messages and integrating with the LangGraph agent

### Message Flow

```
User sends WhatsApp message
    ↓
WhatsApp Business API → Webhook POST /webhook
    ↓
Webhook extracts message text
    ↓
LangGraph ReAct Agent processes message
    ↓
Agent response → WhatsApp Client
    ↓
WhatsApp Business API → User receives response
```

## Production Deployment

For production deployment:

1. **Generate Permanent Access Token:**
   - Go to Meta Business Suite → Business Settings
   - Under "Users," go to "System Users"
   - Create a system user or use existing
   - Generate a new token with `whatsapp_business_messaging` permission
   - Never expires, so store securely

2. **Deploy to a Cloud Platform:**
   - Deploy the FastAPI app to platforms like:
     - Railway.app
     - Render.com
     - Google Cloud Run
     - AWS Lambda (with Mangum adapter)
     - Heroku

3. **Update Webhook URL:**
   - Update the webhook URL in Meta to your production URL
   - Ensure the URL is HTTPS (required by Meta)

4. **Add Your Business Phone Number:**
   - In Meta Business Suite, add and verify your business phone number
   - Update the sender phone number in your configuration

5. **Set Environment Variables:**
   - Configure all environment variables in your production environment
   - Use secrets management for sensitive credentials

## Troubleshooting

### Webhook Verification Fails
- Ensure `WHATSAPP_VERIFY_TOKEN` matches in both `.env` and Meta configuration
- Check that your ngrok URL is correct and accessible
- Verify the server is running on the correct port

### Messages Not Received
- Check webhook subscription includes "messages" field
- Verify access token is valid (not expired)
- Check server logs for errors
- Ensure phone number is added as a test recipient (during testing phase)

### Agent Errors
- Verify all required API keys are set (Anthropic/OpenAI, Tavily)
- Check LangGraph agent configuration in `src/react_agent/context.py`
- Review server logs for detailed error messages

### Rate Limits
- Meta has rate limits on the free tier
- For production, consider upgrading to a paid tier
- Implement rate limiting in your webhook to avoid overwhelming the agent

## Security Considerations

1. **Never commit `.env` file** - It's already in `.gitignore`
2. **Validate webhook signatures** - For production, implement webhook signature verification
3. **Rate limiting** - Add rate limiting to prevent abuse
4. **Input validation** - The current implementation validates basic message structure
5. **Access token security** - Store access tokens securely, rotate regularly

## Next Steps

- Customize the agent's behavior by modifying `src/react_agent/prompts.py`
- Add more tools to the agent in `src/react_agent/tools.py`
- Implement conversation memory to maintain context across messages
- Add support for media messages (images, documents, etc.)
- Implement user authentication/authorization if needed
