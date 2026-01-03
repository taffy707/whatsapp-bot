#!/bin/bash
# Quick start script for WhatsApp Agent

set -e

echo "Starting WhatsApp Agent..."

# Start ngrok in background
echo "Starting ngrok tunnel..."
ngrok http 8000 > /dev/null &
NGROK_PID=$!
sleep 2

# Get ngrok URL
NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'] if d.get('tunnels') else '')")

if [ -z "$NGROK_URL" ]; then
    echo "Failed to start ngrok. Make sure ngrok is installed and configured."
    kill $NGROK_PID 2>/dev/null
    exit 1
fi

echo ""
echo "================================================"
echo "Webhook URL: ${NGROK_URL}/webhook"
echo "================================================"
echo ""
echo "Configure this URL in Meta Business Suite:"
echo "  1. Go to your app > WhatsApp > Configuration"
echo "  2. Edit the webhook and set Callback URL to:"
echo "     ${NGROK_URL}/webhook"
echo ""
echo "Starting webhook server..."
echo "Press Ctrl+C to stop"
echo ""

# Start webhook server (foreground)
python -m uvicorn react_agent.whatsapp_webhook:app --host 0.0.0.0 --port 8000

# Cleanup on exit
trap "kill $NGROK_PID 2>/dev/null" EXIT
