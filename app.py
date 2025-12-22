from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Configuration
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'nasi_kandar_bot_verify_2025')
WHATSAPP_API_URL = 'https://graph.facebook.com/v24.0'

# Webhook verification (required by WhatsApp)
@app.route('/webhook', methods=['GET'])
def verify_webhook():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    if mode and token == VERIFY_TOKEN:
        print('Webhook verified successfully!')
        return challenge, 200
    else:
        return 'Forbidden', 403

# Webhook to receive messages
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        body = request.get_json()
        
        if body.get('object') == 'whatsapp_business_account':
            entry = body.get('entry', [{}])[0]
            changes = entry.get('changes', [{}])[0]
            value = changes.get('value', {})
            messages = value.get('messages', [])
            
            if messages:
                message = messages[0]
                from_number = message.get('from')
                message_body = message.get('text', {}).get('body', '')
                message_id = message.get('id')
                
                print(f'Received message from {from_number}: {message_body}')
                
                # Process and reply to the message
                handle_incoming_message(from_number, message_body)
        
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        print(f'Error processing webhook: {e}')
        return jsonify({'status': 'error'}), 500

# Handle incoming messages and generate replies
def handle_incoming_message(customer_phone, message_text):
    lower_message = message_text.lower().strip()
    reply = ''
    
    # Auto-reply logic based on keywords
    if any(word in lower_message for word in ['hello', 'hi', 'hey']):
        reply = ('Hello! Welcome to Nasi Kandar. How can I help you today?\n\n'
                '1. View Menu\n'
                '2. Order Now\n'
                '3. Check Status\n'
                '4. Contact Support')
    
    elif 'menu' in lower_message:
        reply = ('🍽️ *Our Menu*\n\n'
                '1. Nasi Kandar Special - RM12\n'
                '2. Ayam Goreng - RM8\n'
                '3. Ikan Goreng - RM10\n'
                '4. Sotong Goreng - RM9\n'
                '5. Daging Kari - RM15\n\n'
                'Reply with the item number to order!')
    
    elif 'order' in lower_message or any(char in lower_message for char in '12345'):
        reply = ('Great! To place your order, please provide:\n\n'
                '📍 Your delivery address\n'
                '📞 Contact number\n'
                '🕒 Preferred delivery time\n\n'
                'Or call us at: +60 12-345-6789')
    
    elif 'status' in lower_message:
        reply = ('To check your order status, please provide your order number.\n\n'
                'Format: ORDER-XXXXX')
    
    elif 'hours' in lower_message or 'open' in lower_message:
        reply = ('🕐 *Opening Hours*\n\n'
                'Monday - Sunday: 11:00 AM - 11:00 PM\n\n'
                'We are open every day!')
    
    elif 'location' in lower_message or 'address' in lower_message:
        reply = ('📍 *Our Location*\n\n'
                'Nasi Kandar Restaurant\n'
                'Jalan Penang, Georgetown\n'
                'Pulau Pinang, Malaysia\n\n'
                'Google Maps: [Add your link here]')
    
    elif 'price' in lower_message or 'cost' in lower_message:
        reply = ('Our prices range from RM8 to RM15 per dish.\n\n'
                'Type "menu" to see the full menu with prices.')
    
    elif 'delivery' in lower_message:
        reply = ('🚚 *Delivery Information*\n\n'
                '• Delivery Fee: RM5 (within 5km)\n'
                '• Delivery Time: 30-45 minutes\n'
                '• Minimum Order: RM20\n\n'
                'Ready to order? Type "order" to proceed!')
    
    elif 'thank' in lower_message:
        reply = ('You\'re welcome! Have a great day! 😊\n\n'
                'Feel free to message us anytime.')
    
    else:
        reply = ('Thank you for your message! 🙏\n\n'
                'I can help you with:\n'
                '• Menu and Prices\n'
                '• Place Orders\n'
                '• Delivery Information\n'
                '• Opening Hours\n'
                '• Location\n\n'
                'Just type what you need (e.g., "menu", "order", "delivery")')
    
    # Send reply to customer
    send_whatsapp_message(customer_phone, reply)

# Send message via WhatsApp API
def send_whatsapp_message(to, message):
    try:
        url = f'{WHATSAPP_API_URL}/{PHONE_NUMBER_ID}/messages'
        
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'text',
            'text': {
                'body': message
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        
        print(f'Message sent successfully: {response.json()}')
        return response.json()
    except Exception as e:
        print(f'Error sending message: {e}')
        if hasattr(e, 'response'):
            print(f'Response: {e.response.text}')
        raise

# Health check endpoint
@app.route('/', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'running',
        'message': 'WhatsApp Bot is active',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.getenv('PORT', 3000))
    print(f'🤖 WhatsApp Bot is running on port {port}')
    print(f'📱 Webhook URL: http://localhost:{port}/webhook')
    app.run(host='0.0.0.0', port=port, debug=True)
