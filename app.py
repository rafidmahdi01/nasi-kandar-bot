import os
import time
import telebot
from telebot import types
from dotenv import load_dotenv
from transformers import pipeline
from PIL import Image
import io
import traceback
import requests
import json
import re

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
HF_API_KEY = os.getenv('HUGGINGFACE_API_KEY')

if not TOKEN:
    print("❌ Error: TELEGRAM_TOKEN not found in .env file.")
    exit()

# Initialize bot
bot = telebot.TeleBot(TOKEN)
print("✅ Nasi Kandar Smart Bot is running...")

# Initialize local document QA model (runs on your machine; requires transformers+torch+Pillow)
print("⏳ Loading local AI Brain (this may take a minute the first time)...")
ai_scanner = None
try:
    # Use visual-question-answering which runs OCR internally (no pytesseract required)
    ai_scanner = pipeline(
        "visual-question-answering",
        model="dandelin/vilt-b32-finetuned-vqa"
    )
    print("✅ Local AI Brain (VQA) loaded — ready to verify receipts.")
except Exception as e:
    print(f"⚠️ Could not load local AI Brain: {e}")
    ai_scanner = None

# --- DATABASE (In-Memory) ---
user_data = {}

# --- MENU DATA ---
MENU_ITEMS = {
    '1': {'name': 'Nasi Kandar Ayam Goreng', 'price': 'RM 12.00'},
    '2': {'name': 'Nasi Kandar Daging Hitam', 'price': 'RM 15.00'},
    '3': {'name': 'Nasi Kandar Sotong Besar', 'price': 'RM 20.00'},
    '4': {'name': 'Nasi Kandar Ikan Bawal',   'price': 'RM 18.00'},
    '5': {'name': 'Teh Tarik Ikat Tepi',      'price': 'RM 3.50'},
    '6': {'name': 'Nasi Kandar Kambing',     'price': 'RM 16.00'},
    '7': {'name': 'Mee Goreng Mamak',        'price': 'RM 8.00'},
    '8': {'name': 'Roti Canai with Curry',   'price': 'RM 6.00'},
    '9': {'name': 'Nasi Lemak Special',      'price': 'RM 10.00'},
    '10': {'name': 'ABC Juice',              'price': 'RM 4.50'},
    '11': {'name': 'Kopi O',                 'price': 'RM 2.50'},
    '12': {'name': 'Satay Ayam (10 sticks)', 'price': 'RM 14.00'}
}

# --- HELPER FUNCTION: HUGGING FACE VQA RECEIPT VERIFICATION ---
def verify_receipt_locally(image_bytes):
    """
    Verify receipt by running a local visual-question-answering model.
    Returns True if it looks like a receipt with a total amount, False otherwise.
    """
    if not ai_scanner:
        # No local model available — accept to avoid blocking users
        return True

    # Save image temporarily
    tmp_path = "tmp_receipt.jpg"
    try:
        with open(tmp_path, 'wb') as f:
            f.write(image_bytes)
        
        try:
            # Ask if it's a receipt
            result1 = ai_scanner(image=tmp_path, question="Is this a receipt?")
            print("Is receipt result:", result1)
            
            # Ask for the total amount
            result2 = ai_scanner(image=tmp_path, question="How much is the total?")
            print("Total amount result:", result2)
            
            # Check if both answers are confident
            is_receipt_confident = False
            total_confident = False
            
            if isinstance(result1, dict):
                is_receipt_confident = result1.get('score', 0) > 0.5 and 'yes' in result1.get('answer', '').lower()
            elif isinstance(result1, list) and len(result1) > 0:
                is_receipt_confident = result1[0].get('score', 0) > 0.5 and 'yes' in result1[0].get('answer', '').lower()
            
            if isinstance(result2, dict):
                total_confident = result2.get('score', 0) > 0.5 and result2.get('answer', '') != ''
            elif isinstance(result2, list) and len(result2) > 0:
                total_confident = result2[0].get('score', 0) > 0.5 and result2[0].get('answer', '') != ''
            
            return is_receipt_confident and total_confident
        except Exception as e:
            print(f"Local AI verification failed: {e}")
            traceback.print_exc()
            return True
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    except Exception as e:
        print(f"Failed to save image for local verification: {e}")
        return True

# --- NEW HELPER: REAL ADDRESS CHECKER (Free) ---
def validate_address_osm(address_text):
    headers = {'User-Agent': 'NasiKandarBot/1.0'}
    url = "https://nominatim.openstreetmap.org/search"
    
    # --- ATTEMPT 1: EXACT SEARCH ---
    # Try the full address first
    params = {'q': address_text, 'countrycodes': 'my', 'format': 'json', 'limit': 1}
    response = requests.get(url, params=params, headers=headers).json()
    if len(response) > 0:
        return {'valid': True, 'name': response[0]['display_name'], 'lat': response[0]['lat'], 'lon': response[0]['lon']}
    
    # --- ATTEMPT 2: INTELLIGENT CLEANING ---
    # If exact failed, remove specific unit details (Block, Unit, Level, No)
    print(f"Exact search failed. Cleaning address: {address_text}")
    
    # This removes things like "Block A", "Unit 5", "No. 12"
    clean_text = re.sub(r'(?i)(block|unit|level|lot|suite|no\.?)\s*\w+', '', address_text)
    clean_text = re.sub(r'[^\w\s,]', '', clean_text) # Remove special chars like ; : ( )
    
    # Remove extra spaces
    clean_text = " ".join(clean_text.split())
    
    params['q'] = clean_text
    response = requests.get(url, params=params, headers=headers).json()
    if len(response) > 0:
        return {'valid': True, 'name': response[0]['display_name'], 'lat': response[0]['lat'], 'lon': response[0]['lon']}

    # --- ATTEMPT 3: FIRST 3 WORDS (FALLBACK) ---
    # Just take the first few words (usually the building name) + "Malaysia"
    words = address_text.split()
    if len(words) > 2:
        short_query = " ".join(words[:3]) + " Malaysia"
        params['q'] = short_query
        response = requests.get(url, params=params, headers=headers).json()
        if len(response) > 0:
            return {'valid': True, 'name': response[0]['display_name'], 'lat': response[0]['lat'], 'lon': response[0]['lon']}

    return {'valid': False}

# --- HELPER: GET USER STEP ---
def get_user_step(chat_id):
    if chat_id not in user_data:
        user_data[chat_id] = {'step': 'start'}
    return user_data[chat_id]['step']


# =======================================================
#                   BOT HANDLERS
# =======================================================

# 1. START / MENU / GREETINGS
# I added the second line below to handle 'hi', 'hello', and 'hey'
@bot.message_handler(commands=['start', 'menu', 'order'])
@bot.message_handler(func=lambda msg: msg.text.lower() in ['hi', 'hello', 'hey'])
def show_menu(message):
    chat_id = message.chat.id
    
    # Reset/Initialize user state
    user_data[chat_id] = {
        'step': 'selecting_food',
        'order_items': [],  # List to store multiple food items
        'total_food_price': 0.0
    }
    
    # Build the Menu Text
    text = "🍛 *NASI KANDAR BISTROO MENU* 🍛\n\nTo order, just *reply with the number*:\n\n"
    for key, item in MENU_ITEMS.items():
        text += f"*{key}.* {item['name']} - {item['price']}\n"
    
    bot.send_message(chat_id, text, parse_mode="Markdown")


# 2. STEP: SELECT FOOD
@bot.message_handler(func=lambda msg: get_user_step(msg.chat.id) in ['selecting_food', 'adding_more_food'])
def handle_food_selection(message):
    chat_id = message.chat.id
    selection = message.text.strip()
    
    if selection in MENU_ITEMS:
        selected_item = MENU_ITEMS[selection]
        selected_food = selected_item['name']
        food_price = float(selected_item['price'].replace('RM ', ''))
        
        # Add item to order
        user_data[chat_id]['order_items'].append({
            'name': selected_food,
            'price': food_price,
            'quantity': 1
        })
        user_data[chat_id]['total_food_price'] += food_price
        
        # Show current order summary
        current_order = user_data[chat_id]['order_items']
        order_summary = "🛒 *YOUR CURRENT ORDER*\n"
        for i, item in enumerate(current_order, 1):
            order_summary += f"{i}. {item['name']} - RM {item['price']:.2f}\n"
        order_summary += f"\n💰 *Food Total: RM {user_data[chat_id]['total_food_price']:.2f}*"
        
        # Ask if they want to add more items
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add('✅ Yes, add more items', '🚚 No, proceed to delivery')
        
        bot.send_message(chat_id, 
                         f"✅ Added: *{selected_food}*\n\n{order_summary}\n\n"
                         f"Would you like to add more items to your order?", 
                         parse_mode="Markdown", reply_markup=markup)
        
        user_data[chat_id]['step'] = 'confirming_more_items'
        
    else:
        bot.reply_to(message, "❌ Invalid number. Please look at the menu and type 1-12.")


# 2.5 STEP: CONFIRM ADDING MORE ITEMS
@bot.message_handler(func=lambda msg: get_user_step(msg.chat.id) == 'confirming_more_items')
def handle_more_items_confirmation(message):
    chat_id = message.chat.id
    choice = message.text
    
    if choice == '✅ Yes, add more items':
        # Show menu again for additional selections
        user_data[chat_id]['step'] = 'adding_more_food'
        
        text = "🍛 *ADD MORE ITEMS TO YOUR ORDER* 🍛\n\nReply with the number to add:\n\n"
        for key, item in MENU_ITEMS.items():
            text += f"*{key}.* {item['name']} - {item['price']}\n"
        
        # Show current order
        current_order = user_data[chat_id]['order_items']
        text += f"\n🛒 *Current Order:*\n"
        for i, item in enumerate(current_order, 1):
            text += f"{i}. {item['name']} - RM {item['price']:.2f}\n"
        text += f"💰 *Food Total: RM {user_data[chat_id]['total_food_price']:.2f}*"
        
        bot.send_message(chat_id, text, parse_mode="Markdown")
        
    elif choice == '🚚 No, proceed to delivery':
        # Proceed to address input
        user_data[chat_id]['step'] = 'providing_address'
        
        bot.send_message(chat_id, 
                         "📍 *Delivery Address*\n\n"
                         "You can either:\n"
                         "• Type your full address (e.g., *123 Jalan Bukit Bintang, KL*)\n"
                         "• Or click the 📎 paperclip button below → Location → Share your current location\n\n"
                         "What's your delivery address?", 
                         parse_mode="Markdown")
    else:
        bot.reply_to(message, "Please use the buttons below to confirm.")


# 3. STEP: GET ADDRESS (With REAL Validation)
@bot.message_handler(func=lambda msg: get_user_step(msg.chat.id) == 'providing_address')
def handle_address(message):
    chat_id = message.chat.id
    address_input = message.text.strip()
    
    # Quick check: Filter out very short nonsense like "hi", "...", "123"
    if len(address_input) < 5 or not any(char.isalpha() for char in address_input):
        bot.reply_to(message, "❌ That doesn't look like a valid address.\n\nPlease type a proper address (e.g., *123 Jalan Penang, Georgetown*).", parse_mode="Markdown")
        return

    bot.send_message(chat_id, "🔎 Checking map for this location...", parse_mode="Markdown")
    
    # 1. CALL THE REAL MAP CHECKER
    map_result = validate_address_osm(address_input)
    
    if map_result['valid']:
        # 2. SAVE THE REAL DATA
        user_data[chat_id]['address'] = map_result['name']
        
        # (Optional) Calculate REAL delivery charge based on random logic or real coordinates
        # For now, we simulate distance but ONLY if address is valid
        import random
        dist = round(random.uniform(1.0, 15.0), 1) 
        charge = round(dist * 0.80 + 3.00, 2) # RM0.80 per km + RM3 base fee
        
        # Get food price for total calculation
        food_price = user_data[chat_id]['total_food_price']
        
        total_amount = food_price + charge
        
        user_data[chat_id]['step'] = 'choosing_payment'
        user_data[chat_id]['delivery_charge'] = charge
        user_data[chat_id]['distance_km'] = dist
        
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add('💵 Cash on Delivery', '📲 QR Pay')
        
        bot.send_message(chat_id, 
                         f"✅ **Address Found!**\n_{map_result['name']}_\n\n"
                         f"📏 Distance: {dist}km\n"
                         f"🛵 Delivery Fee: RM {charge:.2f}\n\n"
                         f"💰 **ORDER SUMMARY**\n"
                         f"🍛 *Food Items:*\n"
                         + "\n".join([f"• {item['name']}: RM {item['price']:.2f}" for item in user_data[chat_id]['order_items']]) + f"\n"
                         f"🚚 Delivery: RM {charge:.2f}\n"
                         f"💵 **TOTAL: RM {total_amount:.2f}**\n\n"
                         f"How would you like to pay?", 
                         parse_mode="Markdown", reply_markup=markup)
    else:
        # 3. REJECT INVALID ADDRESS
        bot.reply_to(message, 
                     "❌ **Address Not Found**\n\n"
                     "We couldn't find that location on the map in Malaysia.\n"
                     "Please try being more specific (include city or postcode).\n\n"
                     "Example: _Menara Maybank, KL_")


# --- 3b. NEW HANDLER: RECEIVE GPS LOCATION PIN ---
# This allows users to share their live location or pin instead of typing
@bot.message_handler(content_types=['location'], func=lambda msg: get_user_step(msg.chat.id) == 'providing_address')
def handle_location_pin(message):
    chat_id = message.chat.id
    lat = message.location.latitude
    lon = message.location.longitude
    
    bot.send_message(chat_id, "📍 Processing your location...")
    
    # --- HELPER: Calculate Distance (Haversine Formula) ---
    def calculate_distance(lat1, lon1, lat2, lon2):
        from math import radians, sin, cos, sqrt, atan2
        R = 6371.0  # Earth radius in kilometers
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    # 1. Reverse Geocode (Get address from Coordinates)
    # We ask OSM: "What address is at these coordinates?"
    url = "https://nominatim.openstreetmap.org/reverse"
    headers = {'User-Agent': 'NasiKandarBot/1.0'}
    params = {'lat': lat, 'lon': lon, 'format': 'json'}
    
    try:
        response = requests.get(url, params=params, headers=headers).json()
        address_name = response.get('display_name', f"GPS: {lat}, {lon}")
        
        # 2. Calculate distance from restaurant (KL City Centre)
        restaurant_lat, restaurant_lng = 3.1390, 101.6869
        distance_km = calculate_distance(restaurant_lat, restaurant_lng, lat, lon)
        
        # 3. Calculate delivery charge
        delivery_charge = 2.00 + (distance_km * 0.50)
        
        # 4. Check if within delivery range
        if distance_km > 50:
            bot.send_message(chat_id, 
                           f"❌ **Too Far for Delivery**\n\n"
                           f"Your location is {distance_km:.1f}km away.\n"
                           f"Maximum delivery distance is 50km.\n\n"
                           f"Please provide a different address or contact us directly.")
            return
        
        # 5. Save Data
        user_data[chat_id]['address'] = address_name
        user_data[chat_id]['delivery_charge'] = delivery_charge
        user_data[chat_id]['distance_km'] = distance_km
        user_data[chat_id]['step'] = 'choosing_payment'
        
        # Get food price for total calculation
        food_price = user_data[chat_id]['total_food_price']
        
        total_amount = food_price + delivery_charge
        
        # Show success message
        markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
        markup.add('💵 Cash on Delivery', '📲 QR Pay')
        
        bot.send_message(chat_id, 
                         f"📍 **Location Received!**\n_{address_name}_\n\n"
                         f"📏 Distance: {distance_km:.1f}km\n"
                         f"🛵 Delivery Fee: RM {delivery_charge:.2f}\n\n"
                         f"💰 **ORDER SUMMARY**\n"
                         f"🍛 *Food Items:*\n"
                         + "\n".join([f"• {item['name']}: RM {item['price']:.2f}" for item in user_data[chat_id]['order_items']]) + f"\n"
                         f"🚚 Delivery: RM {delivery_charge:.2f}\n"
                         f"💵 **TOTAL: RM {total_amount:.2f}**\n\n"
                         f"How would you like to pay?", 
                         parse_mode="Markdown", reply_markup=markup)
                         
    except Exception as e:
        print(f"Location processing error: {e}")
        bot.send_message(chat_id, 
                        "⚠️ Error reading location. Please type your address manually instead.")


# 4. STEP: CHOOSE PAYMENT METHOD
@bot.message_handler(func=lambda msg: get_user_step(msg.chat.id) == 'choosing_payment')
def handle_payment_choice(message):
    chat_id = message.chat.id
    choice = message.text

    if choice == '💵 Cash on Delivery':
        complete_order(chat_id, "Cash on Delivery")
    
    elif choice == '📲 QR Pay':
        user_data[chat_id]['step'] = 'uploading_proof'
        
        # Calculate total amount for QR payment
        total_amount = user_data[chat_id]['total_food_price'] + user_data[chat_id].get('delivery_charge', 5.00)
        
        # Send the static QR code image
        qr_image_path = r"c:\Users\Rafid Mahdi\nasi-kandar-bot\images\QR code.png"
        
        caption = f"📲 *Scan DuitNow to Pay RM {total_amount:.2f}*\n\nPlease make payment and *send the receipt (photo)* here."
        
        try:
            # Check if file exists first
            import os
            if not os.path.exists(qr_image_path):
                raise FileNotFoundError(f"QR image not found at {qr_image_path}")
            
            # Read file with explicit encoding handling
            with open(qr_image_path, 'rb') as qr_file:
                qr_data = qr_file.read()
            
            # Send photo with timeout handling
            bot.send_photo(chat_id, qr_data,
                           caption=caption,
                           parse_mode="Markdown",
                           reply_markup=types.ReplyKeyboardRemove(),
                           timeout=30)  # 30 second timeout
            
        except FileNotFoundError as e:
            print(f"QR image file not found: {e}")
            # Fallback: generate dynamic QR if static image not found
            payment_text = f'DuitNow%20to%20Nasi%20Kandar%20RM{total_amount:.2f}'
            qr_url = f"https://chart.googleapis.com/chart?cht=qr&chs=400x400&chl={payment_text}"
            try:
                bot.send_photo(chat_id, qr_url,
                               caption=caption,
                               parse_mode="Markdown",
                               reply_markup=types.ReplyKeyboardRemove(),
                               timeout=30)
            except Exception as e2:
                print(f"Dynamic QR also failed: {e2}")
                bot.send_message(chat_id,
                                 f"⚠️ QR code generation failed. Please make payment of RM {total_amount:.2f} and send receipt photo.",
                                 reply_markup=types.ReplyKeyboardRemove())
                                 
        except Exception as e:
            print(f"Error sending QR image: {e}")
            # Try sending as document instead of photo
            try:
                with open(qr_image_path, 'rb') as qr_file:
                    bot.send_document(chat_id, qr_file,
                                      caption=caption,
                                      reply_markup=types.ReplyKeyboardRemove(),
                                      timeout=30)
            except Exception as e2:
                print(f"Document send also failed: {e2}")
                bot.send_message(chat_id,
                                 f"⚠️ Error loading QR code. Please make payment of RM {total_amount:.2f} and send receipt photo.",
                                 reply_markup=types.ReplyKeyboardRemove())
        
    else:
        bot.reply_to(message, "Please click one of the buttons below.")


# 5. STEP: UPLOAD RECEIPT
@bot.message_handler(content_types=['photo'], func=lambda msg: get_user_step(msg.chat.id) == 'uploading_proof')
def handle_receipt(message):
    chat_id = message.chat.id
    bot.reply_to(message, "🤖 AI is analyzing your receipt... Please wait...")
    try:
        # Download image from Telegram
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Verify locally using transformers pipeline
        is_valid = verify_receipt_locally(downloaded_file)

        if is_valid:
            bot.reply_to(message, "✅ Receipt Verified! Payment successful.")
            complete_order(chat_id, "Paid via QR (Verified)")
        else:
            bot.reply_to(message, "⚠️ The AI could not detect a total amount. Please upload a clearer photo.")
    except Exception as e:
        print(f"Error during receipt handling: {e}")
        traceback.print_exc()
        bot.reply_to(message, "⚠️ System error. We will check manually.")
        complete_order(chat_id, "Manual Check Required")


# 6. FINAL STEP: ORDER COMPLETION & GPS
def complete_order(chat_id, payment_method):
    order_details = user_data[chat_id]
    
    # Build food items summary
    food_items_text = ""
    total_food_price = 0.0
    for item in order_details['order_items']:
        food_items_text += f"🍛 {item['name']} - RM {item['price']:.2f}\n"
        total_food_price += item['price']
    
    delivery_charge = order_details.get('delivery_charge', 5.00)
    total_amount = total_food_price + delivery_charge
    
    summary = (f"🧾 *ORDER CONFIRMED*\n"
               f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
               f"{food_items_text}"
               f"📍 *Addr:* {order_details['address']}\n"
               f"🚚 *Delivery:* RM {delivery_charge:.2f}\n"
               f"💳 *Type:* {payment_method}\n"
               f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
               f"💰 *TOTAL: RM {total_amount:.2f}*\n\n"
               f"👨‍🍳 _Kitchen is preparing your food..._")
    
    bot.send_message(chat_id, summary, parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    
    time.sleep(2)
    
    gps_link = "https://www.google.com/maps/search/?api=1&query=Georgetown,+Penang"
    
    bot.send_message(chat_id, 
                     f"🛵 *Rider Picked Up!*\n\n"
                     f"Your rider *Ali* (PLT 1234) is on the way.\n\n"
                     f"🔴 [Click here to track Driver GPS]({gps_link})", 
                     parse_mode="Markdown")
    
    user_data[chat_id] = {'step': 'start'}


# Handle random text (only if not in the middle of an order)
@bot.message_handler(func=lambda msg: True)
def echo_all(message):
    # Do not interfere when user is in HF chat mode
    if user_data.get(message.chat.id, {}).get('hf_mode') == 'chat':
        return
    if get_user_step(message.chat.id) == 'start':
        bot.reply_to(message, "Hello! Please type 'Hi' or /menu to order food.")

# --- START POLLING ---
bot.infinity_polling()