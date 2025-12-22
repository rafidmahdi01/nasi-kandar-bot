const express = require('express');
const axios = require('axios');

const app = express();
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const PORT = process.env.PORT || 3000;

// Configuration - Replace with your actual credentials
const CONFIG = {
    WHATSAPP_TOKEN: process.env.WHATSAPP_TOKEN || 'YOUR_WHATSAPP_ACCESS_TOKEN',
    WHATSAPP_PHONE_NUMBER_ID: process.env.PHONE_NUMBER_ID || 'YOUR_PHONE_NUMBER_ID',
    VERIFY_TOKEN: process.env.VERIFY_TOKEN || 'your_verify_token_123',
    WHATSAPP_API_URL: 'https://graph.facebook.com/v18.0'
};

// Webhook verification (required by WhatsApp)
app.get('/webhook', (req, res) => {
    const mode = req.query['hub.mode'];
    const token = req.query['hub.verify_token'];
    const challenge = req.query['hub.challenge'];

    if (mode && token === CONFIG.VERIFY_TOKEN) {
        console.log('Webhook verified successfully!');
        res.status(200).send(challenge);
    } else {
        res.sendStatus(403);
    }
});

// Webhook to receive messages
app.post('/webhook', async (req, res) => {
    try {
        const body = req.body;

        if (body.object === 'whatsapp_business_account') {
            const entry = body.entry?.[0];
            const changes = entry?.changes?.[0];
            const value = changes?.value;
            const messages = value?.messages;

            if (messages && messages.length > 0) {
                const message = messages[0];
                const from = message.from; // Customer's phone number
                const messageBody = message.text?.body || '';
                const messageId = message.id;

                console.log(`Received message from ${from}: ${messageBody}`);

                // Process and reply to the message
                await handleIncomingMessage(from, messageBody);
            }
        }

        res.sendStatus(200);
    } catch (error) {
        console.error('Error processing webhook:', error);
        res.sendStatus(500);
    }
});

// Handle incoming messages and generate replies
async function handleIncomingMessage(customerPhone, messageText) {
    const lowerMessage = messageText.toLowerCase().trim();
    let reply = '';

    // Auto-reply logic based on keywords
    if (lowerMessage.includes('hello') || lowerMessage.includes('hi') || lowerMessage.includes('hey')) {
        reply = 'Hello! Welcome to Nasi Kandar. How can I help you today?\n\n1. View Menu\n2. Order Now\n3. Check Status\n4. Contact Support';
    } 
    else if (lowerMessage.includes('menu')) {
        reply = '🍽️ *Our Menu*\n\n' +
                '1. Nasi Kandar Special - RM12\n' +
                '2. Ayam Goreng - RM8\n' +
                '3. Ikan Goreng - RM10\n' +
                '4. Sotong Goreng - RM9\n' +
                '5. Daging Kari - RM15\n\n' +
                'Reply with the item number to order!';
    }
    else if (lowerMessage.includes('order') || lowerMessage.match(/\b[1-5]\b/)) {
        reply = 'Great! To place your order, please provide:\n\n' +
                '📍 Your delivery address\n' +
                '📞 Contact number\n' +
                '🕒 Preferred delivery time\n\n' +
                'Or call us at: +60 12-345-6789';
    }
    else if (lowerMessage.includes('status')) {
        reply = 'To check your order status, please provide your order number.\n\n' +
                'Format: ORDER-XXXXX';
    }
    else if (lowerMessage.includes('hours') || lowerMessage.includes('open')) {
        reply = '🕐 *Opening Hours*\n\n' +
                'Monday - Sunday: 11:00 AM - 11:00 PM\n\n' +
                'We are open every day!';
    }
    else if (lowerMessage.includes('location') || lowerMessage.includes('address')) {
        reply = '📍 *Our Location*\n\n' +
                'Nasi Kandar Restaurant\n' +
                'Jalan Penang, Georgetown\n' +
                'Pulau Pinang, Malaysia\n\n' +
                'Google Maps: [Add your link here]';
    }
    else if (lowerMessage.includes('price') || lowerMessage.includes('cost')) {
        reply = 'Our prices range from RM8 to RM15 per dish.\n\n' +
                'Type "menu" to see the full menu with prices.';
    }
    else if (lowerMessage.includes('delivery')) {
        reply = '🚚 *Delivery Information*\n\n' +
                '• Delivery Fee: RM5 (within 5km)\n' +
                '• Delivery Time: 30-45 minutes\n' +
                '• Minimum Order: RM20\n\n' +
                'Ready to order? Type "order" to proceed!';
    }
    else if (lowerMessage.includes('thank') || lowerMessage.includes('thanks')) {
        reply = 'You\'re welcome! Have a great day! 😊\n\n' +
                'Feel free to message us anytime.';
    }
    else {
        reply = 'Thank you for your message! 🙏\n\n' +
                'I can help you with:\n' +
                '• Menu and Prices\n' +
                '• Place Orders\n' +
                '• Delivery Information\n' +
                '• Opening Hours\n' +
                '• Location\n\n' +
                'Just type what you need (e.g., "menu", "order", "delivery")';
    }

    // Send reply to customer
    await sendWhatsAppMessage(customerPhone, reply);
}

// Send message via WhatsApp API
async function sendWhatsAppMessage(to, message) {
    try {
        const url = `${CONFIG.WHATSAPP_API_URL}/${CONFIG.WHATSAPP_PHONE_NUMBER_ID}/messages`;
        
        const data = {
            messaging_product: 'whatsapp',
            to: to,
            type: 'text',
            text: {
                body: message
            }
        };

        const response = await axios.post(url, data, {
            headers: {
                'Authorization': `Bearer ${CONFIG.WHATSAPP_TOKEN}`,
                'Content-Type': 'application/json'
            }
        });

        console.log('Message sent successfully:', response.data);
        return response.data;
    } catch (error) {
        console.error('Error sending message:', error.response?.data || error.message);
        throw error;
    }
}

// Health check endpoint
app.get('/', (req, res) => {
    res.json({
        status: 'running',
        message: 'WhatsApp Bot is active',
        timestamp: new Date().toISOString()
    });
});

app.listen(PORT, () => {
    console.log(`🤖 WhatsApp Bot is running on port ${PORT}`);
    console.log(`📱 Webhook URL: http://localhost:${PORT}/webhook`);
});
