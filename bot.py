import telebot
from telebot import types
import time
import os
from flask import Flask, request
import threading

# ==================== YOUR BOT TOKEN ====================
BOT_TOKEN = "8234675036:AAFIWLxSxeaT0-VGt_wUwDySCJbHS_0NTN0"
# ========================================================

bot = telebot.TeleBot(BOT_TOKEN)

# Create Flask app for port binding
app = Flask(__name__)

# Store user data temporarily
user_data = {}

# Available solar panel wattages
SOLAR_PANEL_WATTAGES = [100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750]

# Available battery voltages
BATTERY_VOLTAGES = [12, 12.8, 22.8, 24, 25.6, 36, 48, 51.2, 60, 72, 96, 102.4]

# Battery types
BATTERY_TYPES = ["LiFePO4", "Lead-Acid", "Gel"]

# Product catalog from the image (updated with Dyness battery)
PRODUCT_CATALOG = {
    "Trinasolar": [
        {"Type": "N-Type i-TOPCon Bifacial Dual Glass", "Model": "TSM-NEG21C.20", "Watt": "710W", "Wholesale": "420,000", "Retail": "440,000", "Warranty": "12 Years"},
        {"Type": "N-Type i-TOPCon", "Model": "TSM-NEG19R", "Watt": "620W", "Wholesale": "330,000", "Retail": "340,000", "Warranty": "12 Years"}
    ],
    "Solis": [
        {"Type": "Single Phase", "Model": "S6-EH1P6K-L-Plus", "Capacity": "6 KW", "Wholesale": "3,200,000", "Retail": "3,400,000", "Warranty": "5 Years"},
        {"Type": "Single Phase", "Model": "S6-EH1P8K-L-Plus", "Capacity": "8 KW", "Wholesale": "4,300,000", "Retail": "4,600,000", "Warranty": "5 Years"},
        {"Type": "Single Phase", "Model": "S6-EH1P12K03-NV-YD-L", "Capacity": "12 KW", "Wholesale": "6,350,000", "Retail": "6,750,000", "Warranty": "5 Years"},
        {"Type": "Three Phase", "Model": "S6-EH3P12K02-NV-YD-L", "Capacity": "12 KW", "Wholesale": "6,450,000", "Retail": "6,850,000", "Warranty": "5 Years"},
        {"Type": "Three Phase", "Model": "S6-EH3P15K02-NV-YD-L", "Capacity": "15 KW", "Wholesale": "7,300,000", "Retail": "7,700,000", "Warranty": "5 Years"}
    ],
    "Dyness": [
        {"Type": "Low Voltage Battery", "Model": "POWER BRICK", "Capacity": "51.2V, 280Ah", "Wholesale": "7,190,000", "Retail": "7,490,000", "Warranty": "5+5 Years"}
    ]
}

# Step 1: Calculate total daily energy consumption
def calculate_daily_consumption(total_w, hours):
    return total_w * hours

# Step 2: Calculate battery size based on battery type
def calculate_battery_size(daily_wh, battery_voltage, battery_type="lifepo4"):
    if battery_type.lower() == "lifepo4":
        dod_factor = 0.8
        battery_ah = (daily_wh / battery_voltage) * (1 / dod_factor)
    elif battery_type.lower() == "gel":
        dod_factor = 0.6
        battery_ah = (daily_wh / battery_voltage) * (1 / dod_factor)
    else:
        dod_factor = 0.5
        battery_ah = (daily_wh / battery_voltage) * (1 / dod_factor)
    return battery_ah, dod_factor

# Step 3: Calculate solar panel requirements
def calculate_solar_panels(daily_wh, panel_wattage, sun_hours=5, efficiency=0.85):
    solar_w = (daily_wh / sun_hours) * (1 / efficiency)
    num_panels = round(solar_w / panel_wattage)
    if num_panels < 1:
        num_panels = 1
    return solar_w, num_panels

# Step 4: Calculate inverter size
def calculate_inverter_size(total_w):
    inverter_w = total_w * 1.3
    return inverter_w

# Step 5: Calculate charge controller size
def calculate_charge_controller(solar_w, battery_voltage):
    controller_amps = (solar_w / battery_voltage) * 1.25
    if solar_w <= 1000 and battery_voltage <= 24:
        controller_type = "PWM"
    else:
        controller_type = "MPPT"
    return controller_type, controller_amps

# Function to calculate with specific products
def calculate_with_specific_products(total_w, hours):
    daily_wh = calculate_daily_consumption(total_w, hours)
    
    # Use Trinasolar 710W panel
    panel_wattage = 710
    solar_w, num_panels = calculate_solar_panels(daily_wh, panel_wattage)
    
    # Use Dyness battery (51.2V, 280Ah)
    battery_voltage = 51.2
    battery_capacity_ah = 280
    battery_wh = battery_voltage * battery_capacity_ah
    
    # Calculate how many batteries needed
    batteries_needed = max(1, round(daily_wh / (battery_wh * 0.8)))  # Using 80% DOD for LiFePO4
    
    # Calculate inverter size
    inverter_w = calculate_inverter_size(total_w)
    
    # Find suitable Solis inverter
    suitable_inverter = None
    for inverter in PRODUCT_CATALOG["Solis"]:
        capacity_kw = float(inverter["Capacity"].split()[0])
        if capacity_kw * 1000 >= inverter_w:
            suitable_inverter = inverter
            break
    
    # If no suitable inverter found, use the largest one
    if not suitable_inverter:
        suitable_inverter = PRODUCT_CATALOG["Solis"][-1]
    
    # Calculate charge controller
    controller_type, controller_amps = calculate_charge_controller(solar_w, battery_voltage)
    
    # Calculate total cost (only retail prices)
    panel_cost = num_panels * int(PRODUCT_CATALOG["Trinasolar"][0]["Retail"].replace(",", ""))
    battery_cost = batteries_needed * int(PRODUCT_CATALOG["Dyness"][0]["Retail"].replace(",", ""))
    inverter_cost = int(suitable_inverter["Retail"].replace(",", ""))
    total_cost = panel_cost + battery_cost + inverter_cost
    
    return {
        "daily_wh": daily_wh,
        "panel_wattage": panel_wattage,
        "num_panels": num_panels,
        "battery_voltage": battery_voltage,
        "battery_capacity_ah": battery_capacity_ah,
        "batteries_needed": batteries_needed,
        "inverter_w": inverter_w,
        "suitable_inverter": suitable_inverter,
        "controller_type": controller_type,
        "controller_amps": controller_amps,
        "panel_cost": panel_cost,
        "battery_cost": battery_cost,
        "inverter_cost": inverter_cost,
        "total_cost": total_cost
    }

@app.route('/')
def home():
    return "Solar Calculator Bot is running!"

# Webhook route for Telegram
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# Set webhook on startup
def set_webhook():
    # Get your Render app URL
    render_url = os.environ.get('RENDER_EXTERNAL_URL', 'https://hsuchoflask.onrender.com')
    webhook_url = f"{render_url}/webhook"
    
    try:
        bot.remove_webhook()
        time.sleep(1)
        bot.set_webhook(url=webhook_url)
        print(f"Webhook set to: {webhook_url}")
    except Exception as e:
        print(f"Error setting webhook: {e}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    try:
        welcome_text = """
☀️ *Hsu Cho Solar Calculator Bot မှ ကြိုဆိုပါတယ်!*

ဆိုလာစနစ်တွက်ချက်မှုအတွက် အဆင့် ၅ ဆင့်ဖြင့် တွက်ချက်ပေးပါမယ်:

1. စုစုပေါင်းစွမ်းအင်သုံးစွဲမှု
2. ဘက်ထရီအရွယ်အစား
3. ဆိုလာပြားလိုအပ်ချက်
4. အင်ဗာတာအရွယ်အစား
5. Charger Controller
        """
        
        # Create inline keyboard with "တွက်ချက်မည်" button
        markup = types.InlineKeyboardMarkup()
        calculate_button = types.InlineKeyboardButton("🔢 တွက်ချက်မည်", callback_data='start_calculation')
        markup.add(calculate_button)
        
        bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown', reply_markup=markup)
        
    except Exception as e:
        print("Error in start:", e)

# Callback handler for the calculate button
@bot.callback_query_handler(func=lambda call: call.data == 'start_calculation')
def handle_calculate_callback(call):
    try:
        chat_id = call.message.chat.id
        user_data[chat_id] = {}
        
        # Ask if user knows total wattage with inline keyboard
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton("✅ သိပါသည်", callback_data='know_wattage_yes'),
            types.InlineKeyboardButton("❌ မသိပါ", callback_data='know_wattage_no')
        ]
        markup.add(*buttons)
        
        bot.send_message(chat_id, "🔌 *သင့်စုစုပေါင်းဝပ်အား (W) ကိုသိပါသလား?*", 
                        reply_markup=markup, parse_mode='Markdown')
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print("Error in callback handler:", e)
        bot.answer_callback_query(call.id, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်", show_alert=True)

# Callback handler for wattage knowledge
@bot.callback_query_handler(func=lambda call: call.data.startswith('know_wattage_'))
def handle_wattage_knowledge_callback(call):
    try:
        chat_id = call.message.chat.id
        
        if call.data == 'know_wattage_yes':
            # Ask for total wattage
            msg = bot.send_message(chat_id, "🔌 *ကျေးဇူးပြု၍ စုစုပေါင်းဝပ်အား (W) ထည့်ပါ*\n\nဥပမာ: 500", parse_mode='Markdown')
            bot.register_next_step_handler(msg, ask_usage_hours)
            
        elif call.data == 'know_wattage_no':
            # Send wattage guide
            wattage_guide = """
*အဆင့် 1- သင့်စွမ်းအင်သုံးစွဲမှုကို အကဲဖြတ်ခြင်း။*

*HP to Watt Conversion:*
- 1 HP = 746 Watt
- 1.5 HP = 1119 Watt  
- 2 HP = 1492 Watt
- 3 HP = 2238 Watt
- 5 HP = 3730 Watt
- 10 HP = 7460 Watt

*ပစ္စည်းစာရင်းများကြည့်ရန်:*

🏠 *အိမ်သုံးပစ္စည်း များ:*
- LED မီးသီး (10W): 10-15W
- ပန်ကာ (သေးငယ်သော): 50-75W
- ပန်ကာ (ကြီး�မားသော): 75-100W
- တီဗီ (LED 32-inch): 30-50W
- တီဗီ (LED 55-inch): 60-100W
- ရေခဲသေတ္တာ (သေးငယ်သော): 100-150W
- ရေခဲသေတ္တာ (ပုံမှန်): 150-250W
- ရေခဲသေတ္တာ (ကြီး�မားသော): 250-350W
- မိုက်ခရိုဝေ့ဖ်: 800-1200W
- လျှပ်စစ်အိုး: 1000-1500W
- ရေနွေးအိုး: 1500-2000W
- လေအေးပေးစက် (1 HP): 746W
- လေအေးပေးစက် (1.5 HP): 1119W
- လေအေးပေးစက် (2 HP): 1492W
- ကြိတ်စက်: 300-500W
- အဝတ်�လျှော်စက်: 500-1000W
- အဝတ်ခြောက်စက်: 1000-1500W

🏢 *ရုံးသုံးပစ္စည်း များ:*
- ကွန်ပျူတာ (Desktop): 200-300W
- ကွန်ပျူတာ (Laptop): 50-100W
- ပရင်တာ: 50-150W
- မော်နီတာ: 20-50W
- ပရိုဂျက်တာ: 200-300W
- ဖက်စ်စက်: 50-100W
- ရုံးမီးသီးများ: 20-40W
- ရုံးပန်ကာများ: 75-150W

🏭 *စက်ရုံသုံးပစ္စည်း များ:*
- ပန်ကာ (စက်ရုံ): 200-500W
- မီးသီး (စက်ရုံ): 50-100W
- ပန့်အား (သေးငယ်သော): 750-1500W
- ပန့်အား (အလတ်စား): 1500-3000W
- ပန့်အား (ကြီး�မားသော): 3000-5000W
- ကွန်ပရက်ဆာ (သေးငယ်သော): 1000-2000W
- ကွန်ပရက်ဆာ (အလတ်စား): 2000-4000W
- ကွန်ပရက်ဆာ (ကြီး�မားသော): 4000-7500W
- ဂျင်နရေတာ (အရန်သုံး): 500-2000W
- လျှပ်�စစ် ကိရိယာများ: 500-3000W
- စက်ကိရိယာများ: 1000-5000W

*တွက်ချက် နည်း:*
*Watt (W) = Voltage (V) × Current (A)*
*စုစုပေါင်း ဝပ်အား = ပစ္စည်း တစ်ခုချင်း�စီ၏ ဝပ်အား ပေါင်းခြင်း*

*ဥပမာ ၁ (အိမ်သုံး):*
- LED မီးသီး ၁၀ လုံး (10W) = 10 × 10W = 100W
- ပန်ကာ ၂ လုံး (75W) = 2 × 75W = 150W  
- တီဗီ ၁ လုံး (100W) = 1 × 100W = 100W
- စုစုပေါင်း = 100W + 150W + 100W = 350W

*ဥပမာ ၂ (စက်ရုံသုံး):*
- ပန်ကာ ၅ လုံး (300W) = 5 × 300W = 1500W
- မီးသီး ၂၀ လုံး (50W) = 20 × 50W = 1000W
- စက်ကိရိယာ (2000W) = 1 × 2000W = 2000W
- စုစုပေါင်း = 1500W + 1000W + 2000W = 4500W

🔌 *ကျေးဇူးပြု၍ စုစုပေါင်းဝပ်အား (W) ထည့်ပါ*\n\nဥပမာ: 1500
            """
            msg = bot.send_message(chat_id, wattage_guide, parse_mode='Markdown')
            bot.register_next_step_handler(msg, ask_usage_hours)
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print("Error in wattage knowledge callback:", e)
        bot.answer_callback_query(call.id, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်", show_alert=True)

def ask_usage_hours(message):
    try:
        chat_id = message.chat.id
        total_w = int(message.text)
        
        if total_w <= 0:
            bot.reply_to(message, "❌ ဝပ်အားသည် 0 ထက်ကြီးရပါမယ်")
            return
            
        user_data[chat_id]['total_w'] = total_w
        msg = bot.reply_to(message, f"⏰ *တစ်ရက်ကိုဘယ်နှစ်နာရီသုံးမှာလဲ?*\n\nဥပမာ: 6", parse_mode='Markdown')
        bot.register_next_step_handler(msg, process_hours_input)
    except ValueError:
        bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ဂဏန်းမှန်မှန်ထည့်ပါ\n\nဥပမာ: 500")
    except Exception as e:
        print("Error in ask_usage_hours:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

def process_hours_input(message):
    try:
        chat_id = message.chat.id
        hours = float(message.text)
        
        if hours <= 0 or hours > 24:
            bot.reply_to(message, "❌ သုံးမည့်နာရီသည် 1 မှ 24 ကြား ရှိရပါမယ်")
            return
            
        user_data[chat_id]['hours'] = hours
        
        # Ask product selection with inline keyboard
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton("🏭 A To Z ပစ္စည်းသုံးမည်", callback_data='product_a_to_z'),
            types.InlineKeyboardButton("🔧 အခြားပစ္စည်းသုံးမည်", callback_data='product_other')
        ]
        markup.add(*buttons)
        
        bot.send_message(chat_id, "🔧 *ဘယ်လိုပစ္စည်းတွေသုံးမှာလဲ?*", 
                        reply_markup=markup, parse_mode='Markdown')
        
    except ValueError:
        bot.reply_to(message, "❌ ကျေးဇူးပြု၍ ဂဏန်းမှန်မှန်ထည့်ပါ\n\nဥပမာ: 6")
    except Exception as e:
        print("Error in process_hours_input:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

# Callback handler for product selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('product_'))
def handle_product_selection_callback(call):
    try:
        chat_id = call.message.chat.id
        
        if call.data == 'product_a_to_z':
            # Process A To Z products
            if chat_id in user_data and 'total_w' in user_data[chat_id] and 'hours' in user_data[chat_id]:
                total_w = user_data[chat_id]['total_w']
                hours = user_data[chat_id]['hours']
                
                # Calculate with specific products
                result = calculate_with_specific_products(total_w, hours)
                
                # Format the result
                response = f"""
📊 *Hsu Cho Solar Calculator - တွက်ချက်မှုရလဒ်များ (A To Z ပစ္စည်းများဖြင့်)*

📝 *စွမ်းအင်သုံးစွဲမှုစာရင်း:*
• *စုစုပေါင်းဝပ်အား:* {total_w}W
• *နေ့စဉ်သုံး စွဲမည့်နာရီ:* {hours}h
• *စုစုပေါင်း စွမ်းအင်သုံးစွဲမှု:* {result['daily_wh']:.0f} Wh/ရက်

🏭 *အကြံပြုထားသော ပစ္စည်းများ:*

☀️ *ဆိုလာပြား (Trinasolar):*
   - {result['num_panels']} ချပ် × {PRODUCT_CATALOG['Trinasolar'][0]['Model']} ({PRODUCT_CATALOG['Trinasolar'][0]['Watt']})
   - စျေးနှုန်း: {result['panel_cost']:,} ကျပ်
   - အမျိုးအစား: {PRODUCT_CATALOG['Trinasolar'][0]['Type']}
   - အာမခံ: {PRODUCT_CATALOG['Trinasolar'][0]['Warranty']}

🔋 *ဘက်ထရီ (Dyness):*
   - {result['batteries_needed']} �လုံး × {PRODUCT_CATALOG['Dyness'][0]['Model']} ({PRODUCT_CATALOG['Dyness'][0]['Capacity']})
   - စျေးနှုန်း: {result['battery_cost']:,} ကျပ်
   - အမျိုးအစား: {PRODUCT_CATALOG['Dyness'][0]['Type']}
   - အာမခံ: {PRODUCT_CATALOG['Dyness'][0]['Warranty']}

⚡ *အင်ဗာတာ (Solis):*
   - 1 လုံး × {result['suitable_inverter']['Model']} ({result['suitable_inverter']['Capacity']})
   - စျေးနှုန်း: {result['inverter_cost']:,} ကျပ်
   - အမျိုးအစား: {result['suitable_inverter']['Type']}
   - အာမခံ: {result['suitable_inverter']['Warranty']}

💰 *စုစုပေါင်းကုန်ကျစရိတ်:* {result['total_cost']:,} ကျပ်

💡 *အထူးအကြံပြုချက်များ:*
   - *LiFePO4 ဘက်ထရီများသည် သက်တမ်း�ရှည်ပြီး စိတ်ချရမှုရှိသည်*
   - *80% Depth of Discharge အထိ အသုံးပြုနိုင်ပါသည်*
   - *ဆိုလာပြားများကို နေရောင်ကောင်းစွာရသော နေရာတွင် တပ်ဆင်ပါ*
   - *အင်ဗာတာကို လေဝင်�လေထွက်ကောင်းသော နေရာတွင် ထားရှိပါ*

                """
                
                # Add "Calculate Again" button
                markup = types.InlineKeyboardMarkup()
                again_button = types.InlineKeyboardButton("🔄 ထပ်တွက်ရန်", callback_data='start_calculation')
                markup.add(again_button)
                
                bot.send_message(chat_id, response, parse_mode='Markdown', reply_markup=markup)
                
        elif call.data == 'product_other':
            # Process other products - ask for battery type
            markup = types.InlineKeyboardMarkup(row_width=2)
            buttons = []
            for b_type in BATTERY_TYPES:
                # Use underscores instead of hyphens for callback data
                callback_data = f'battery_type_{b_type.lower().replace(" ", "_").replace("-", "_")}'
                buttons.append(types.InlineKeyboardButton(b_type, callback_data=callback_data))
            markup.add(*buttons)
            
            bot.send_message(chat_id, "🔋 *ဘက်ထရီအမျိုးအစားရွေးချယ်ပါ*", 
                            reply_markup=markup, parse_mode='Markdown')
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print("Error in product selection callback:", e)
        bot.answer_callback_query(call.id, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်", show_alert=True)

# Callback handler for battery type selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('battery_type_'))
def handle_battery_type_callback(call):
    try:
        chat_id = call.message.chat.id
        battery_type_key = call.data.replace('battery_type_', '')
        
        # Convert back to proper battery type name
        battery_type_mapping = {
            'lifepo4': 'LiFePO4',
            'lead_acid': 'Lead-Acid',
            'gel': 'Gel'
        }
        
        battery_type = battery_type_mapping.get(battery_type_key)
        
        if not battery_type:
            bot.answer_callback_query(call.id, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်", show_alert=True)
            return
            
        user_data[chat_id]['battery_type'] = battery_type
        
        # Ask for solar panel wattage
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(f"{wattage}W", callback_data=f'panel_{wattage}') for wattage in SOLAR_PANEL_WATTAGES]
        markup.add(*buttons)
        
        bot.send_message(chat_id, "☀️ *ဆိုလာပြား Wattage ရွေးချယ်ပါ*", 
                        reply_markup=markup, parse_mode='Markdown')
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print("Error in battery type callback:", e)
        bot.answer_callback_query(call.id, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်", show_alert=True)

# Callback handler for solar panel selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('panel_'))
def handle_solar_panel_callback(call):
    try:
        chat_id = call.message.chat.id
        panel_wattage = int(call.data.replace('panel_', ''))
        
        if panel_wattage not in SOLAR_PANEL_WATTAGES:
            bot.answer_callback_query(call.id, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်", show_alert=True)
            return
            
        user_data[chat_id]['panel_wattage'] = panel_wattage
        
        # Ask for battery voltage
        markup = types.InlineKeyboardMarkup(row_width=3)
        buttons = [types.InlineKeyboardButton(f"{voltage}V", callback_data=f'voltage_{voltage}') for voltage in BATTERY_VOLTAGES]
        markup.add(*buttons)
        
        bot.send_message(chat_id, "⚡ *ဘက်ထရီဗို့အားရွေးချယ်ပါ*", 
                        reply_markup=markup, parse_mode='Markdown')
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print("Error in solar panel callback:", e)
        bot.answer_callback_query(call.id, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်", show_alert=True)

# Callback handler for battery voltage selection
@bot.callback_query_handler(func=lambda call: call.data.startswith('voltage_'))
def handle_battery_voltage_callback(call):
    try:
        chat_id = call.message.chat.id
        battery_voltage = float(call.data.replace('voltage_', ''))
        
        if battery_voltage not in BATTERY_VOLTAGES:
            bot.answer_callback_query(call.id, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်", show_alert=True)
            return
        
        # Get all stored data
        total_w = user_data[chat_id]['total_w']
        hours = user_data[chat_id]['hours']
        panel_wattage = user_data[chat_id]['panel_wattage']
        battery_type = user_data[chat_id]['battery_type']
        
        # Perform calculations
        daily_wh = calculate_daily_consumption(total_w, hours)
        battery_ah, dod_factor = calculate_battery_size(daily_wh, battery_voltage, battery_type.lower())
        solar_w, num_panels = calculate_solar_panels(daily_wh, panel_wattage)
        inverter_w = calculate_inverter_size(total_w)
        controller_type, controller_amps = calculate_charge_controller(solar_w, battery_voltage)
        
        # Format result
        result = f"""
📊 *Hsu Cho Solar Calculator - တွက်ချက်မှုရလဒ်များ*

🔋 *ဘက်ထရီအမျိုးအစား:* {battery_type}
⚡ *ဘက်ထရီဗို့အား:* {battery_voltage}V
☀️ *ဆိုလာပြား:* {panel_wattage}W
        
📝 *စွမ်းအင်သုံးစွဲမှုစာရင်း:*
• *စုစုပေါင်း ဝပ်အား:* {total_w}W
• *နေ့စဉ်သုံး စွဲမည့်နာရီ:* {hours}h
• *စုစုပေါင်း စွမ်းအင်သုံးစွဲမှု:* {daily_wh:.0f} Wh/ရက်

🔋 *ဘက်ထရီအရွယ်အစား:* _{battery_ah:.0f} Ah {battery_voltage}V_
   - {battery_type} ဘက်ထရီ (DOD: {dod_factor*100:.0f}%)
   - {battery_ah:.0f}Ah ဘက်ထရီ ၁လုံး (သို့) သေးငယ်သောဘက်ထရီများကို parallel ချိတ်ဆက်အသုံးပြုနိုင်သည်

☀️ *ဆိုလာပြားလိုအပ်ချက်:* _{solar_w:.0f} W_
   - {panel_wattage}W ဆိုလာပြား {num_panels} ချပ်

⚡ *အင်ဗာတာအရွယ်အစား:* _{inverter_w:.0f} W Pure Sine Wave_
   - စုစုပေါင်း ဝပ်အားထက် 30% ပိုကြီးသော အင်ဗာတာရွေးချယ်ထားသည်

🎛️ *Charger Controller:* _{controller_type} {controller_amps:.1f}A_
   - {controller_type} controller {controller_amps:.1f}A အရွယ်အစား

💡 *အထူးအကြံပြုချက်များ:*
"""
        
        if battery_type.lower() == "lifepo4":
            result += """
   - *LiFePO4 ဘက်ထရီများသည် သက်တမ်းရှည်ပြီး စိတ်ချရမှုရှိသည်*
   - *80% Depth of Discharge အထိ အသုံးပြုနိုင်ပါသည်*
"""
        elif battery_type.lower() == "gel":
            result += """
   - *Gel ဘက်ထရီများသည် maintenance-free ဖြစ်ပြီး အတွင်းပိုင်းဖိအားနည်းပါသည်*
   - *60% Depth of Discharge အထိ အသုံးပြုနိုင်ပါသည်*
"""
        else:
            result += """
   - *Lead-Acid ဘက်ထရီများသည် စျေးနှုန်းချိုသာပြီး ရေပြန်ဖြည့်ရန် လိုအပ်ပါသည်*
   - *50% Depth of Discharge အထိ အသုံးပြုနိုင်ပါသည်*
"""
        
        result += """
   - *ဆိုလာပြားများကို နေရောင်ကောင်းစွာရသော နေရာတွင် တပ်ဆင်ပါ*
   - *အင်ဗာတာကို လေဝင်လေထွက်ကောင်းသော နေရာတွင် ထားရှိပါ*
"""
        
        # Add "Calculate Again" button
        markup = types.InlineKeyboardMarkup()
        again_button = types.InlineKeyboardButton("🔄 ထပ်တွက်ရန်", callback_data='start_calculation')
        markup.add(again_button)
        
        bot.send_message(chat_id, result, parse_mode='Markdown', reply_markup=markup)
        
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        print("Error in battery voltage callback:", e)
        bot.answer_callback_query(call.id, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်", show_alert=True)

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = """
*အဆင့်ဆင့်ဆိုလာစနစ်�တွက်ချက်နည်း*

တွက်ချက်ရန် ခလုတ်ကိုနှိပ်ပါ
        """
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['calculate'])
def start_calculation_command(message):
    """Handle /calculate command"""
    try:
        user_data[message.chat.id] = {}
        
        # Ask if user knows total wattage with inline keyboard
        markup = types.InlineKeyboardMarkup(row_width=2)
        buttons = [
            types.InlineKeyboardButton("✅ သိပါသည်", callback_data='know_wattage_yes'),
            types.InlineKeyboardButton("❌ မသိပါ", callback_data='know_wattage_no')
        ]
        markup.add(*buttons)
        
        bot.send_message(message.chat.id, "🔌 *သင့်စုစုပေါင်း�ဝပ်အား (W) ကိုသိပါသလား?*", 
                        reply_markup=markup, parse_mode='Markdown')
    except Exception as e:
        print("Error in calculate command:", e)
        bot.reply_to(message, "❌ အမှားတစ်ခုဖြစ်နေပါတယ်")

if __name__ == "__main__":
    # Set webhook on startup
    set_webhook()
    
    # Start Flask app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
