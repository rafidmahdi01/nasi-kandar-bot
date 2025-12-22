# WhatsApp Auto-Reply Bot

A Node.js bot that automatically replies to customer messages on WhatsApp.

## Features
- ✅ Auto-reply to common customer questions
- ✅ Menu display
- ✅ Order information
- ✅ Business hours & location
- ✅ Delivery information
- ✅ Customizable responses

## Setup Instructions

### 1. Install Dependencies
```bash
npm install
```

### 2. Configure WhatsApp Business API

1. Go to [Meta for Developers](https://developers.facebook.com/)
2. Create a new app or use existing one
3. Add WhatsApp product to your app
4. Get your credentials:
   - Access Token
   - Phone Number ID
   - Create a Verify Token (custom string)

### 3. Set Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

Edit `.env` with your actual values:
```
WHATSAPP_TOKEN=your_actual_token
PHONE_NUMBER_ID=your_phone_id
VERIFY_TOKEN=your_verify_token
PORT=3000
```

### 4. Run the Bot

```bash
node bot.js
```

Or with auto-restart:
```bash
npm install -g nodemon
nodemon bot.js
```

### 5. Configure Webhook

1. Deploy your bot (use ngrok for testing or deploy to cloud)
2. In Meta for Developers > WhatsApp > Configuration:
   - Webhook URL: `https://your-domain.com/webhook`
   - Verify Token: (same as in your .env)
3. Subscribe to messages webhook

## Testing Locally with ngrok

```bash
# Install ngrok
npm install -g ngrok

# Run your bot
node bot.js

# In another terminal, expose your local server
ngrok http 3000

# Use the ngrok URL (https://xxxx.ngrok.io/webhook) in Meta dashboard
```

## Customizing Replies

Edit the `handleIncomingMessage()` function in `bot.js` to customize:
- Keywords
- Responses
- Menu items
- Business information

## Auto-Reply Keywords

Current keywords the bot responds to:
- `hello`, `hi`, `hey` - Greeting
- `menu` - Show menu
- `order` - Order instructions
- `status` - Check order status
- `hours`, `open` - Opening hours
- `location`, `address` - Business location
- `price`, `cost` - Pricing info
- `delivery` - Delivery information
- `thank`, `thanks` - Thank you response

## Project Structure

```
nasi-kandar-bot/
├── bot.js           # Main bot application
├── .env             # Environment variables (create this)
├── .env.example     # Example environment file
├── package.json     # Dependencies
└── README.md        # This file
```

## Deployment Options

- **Heroku**: Free tier with easy deployment
- **Railway**: Modern hosting platform
- **DigitalOcean**: Droplet or App Platform
- **AWS EC2**: Full control
- **Vercel/Netlify**: Serverless functions

## Support

For WhatsApp Business API help:
- [Official Docs](https://developers.facebook.com/docs/whatsapp)
- [WhatsApp Business API](https://business.whatsapp.com/)

## License

ISC
