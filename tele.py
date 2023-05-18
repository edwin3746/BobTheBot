import feedparser
import telegram
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, InlineQueryHandler
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
import time
import json
import datetime
import schedule
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import pytz
import requests

local_tz = pytz.timezone('Asia/Singapore')
current_date = datetime.datetime.now()
formatted_date = current_date.strftime("%d %B %Y")

# Replace 'YOUR_BOT_TOKEN' with the token provided by BotFather
bot_token = '6205012152:AAF8Z3vdKl8x536-VQyPH2fV5Q-dAIyVatQ'

# Replace 'FEED_URL' with the actual RSS feed URL
feed_url = 'https://www.bleepingcomputer.com/feed/'

# Function to get the current time in your local time zone
def get_local_time():
    utc_now = datetime.datetime.now(pytz.utc)
    local_now = utc_now.astimezone(local_tz)
    return local_now

# Function to get the next occurrence of a specific time in your local time zone
def get_next_occurrence(hour, minute):
    now = get_local_time()
    next_occurrence = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_occurrence <= now:
        next_occurrence += datetime.timedelta(days=1)
    return next_occurrence
    
# Save subscribers to json file
def save_subscribers(subscribers):
    with open('subscribers.json', 'w') as file:
        json.dump(subscribers, file)


# Load subscribers from json file
def load_subscribers():
    try:
        with open('subscribers.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


# Function to save preferences to json file
def save_preferences(preferences):
    with open('preferences.json', 'w') as file:
        json.dump(preferences, file)


# Function to load preferences from json file
def load_preferences():
    try:
        with open('preferences.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


# Function to send articles to subscribers based on frequency preference
def send_articles():
    # Fetch and parse the RSS feed
    feed = feedparser.parse(feed_url)

    # Load preferences and subscribers
    preferences = load_preferences()
    subscribers = load_subscribers()

    # Dictionary to track the number of articles sent per day for each user
    articles_sent_per_day = {}

    # Iterate over the feed items and send them to the subscribers
    for entry in feed.entries:
        title = entry.title
        description = entry.description
        link = entry.link
        entry_date = entry.published

        # Convert entry_date to a datetime object
        entry_date = datetime.datetime.strptime(entry_date, "%a, %d %b %Y %H:%M:%S %z")

        # Send the feed item as a message to subscribers based on their preferences
        for chat_id, frequency in preferences.items():
            if frequency.isdigit() and chat_id in subscribers:
                num_articles = int(frequency)

                # Check if the maximum number of articles per day has been reached for the user
                if articles_sent_per_day.get(chat_id, 0) >= num_articles:
                    continue  # Skip sending articles for this user

                # Send the corresponding number of articles without exceeding the maximum
                articles_to_send = min(num_articles, 3 - articles_sent_per_day.get(chat_id, 0))
                for _ in range(articles_to_send):
                    message = f"{title}\n{description}\n{link}"
                    bot.send_message(chat_id=chat_id, text=message)

                # Update the number of articles sent per day for the user
                articles_sent_per_day[chat_id] = articles_sent_per_day.get(chat_id, 0) + articles_to_send
    
def get_latest_news():
    base_url = 'https://www.csa.gov.sg/alerts-advisories'
    response = requests.get(base_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('a', class_='m-card-article')
    
    preferences = load_preferences()

    for article in articles:
        href = article.get('href')
        news_url = urljoin(base_url, href)
        response = requests.get(news_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract date from published article
        note_text = soup.find('p', class_='m-card-article__note').text
        date = note_text.split('|')[0].strip()
        date = date.replace("Published on ", "")
        
        if date == formatted_date:
            keys = preferences.keys()
            for key in keys:
                message1 = "Latest Alert & Advisories: " + news_url
                bot.send_message(chat_id=key, text=message1)
        else:
            print("Old news la!")
            exit(0)
            
            
            
# Function to handle the /subscribe command
def subscribe(update, context):
    chat_id = update.message.chat_id
    if chat_id not in subscribers:
        subscribers[chat_id] = None  # Update chatID of new subscriber
        context.bot.send_message(chat_id=chat_id,
                                 text="You have subscribed to feed updates. You can choose the frequency of articles per day via the /frequency command.")
        save_subscribers(subscribers)
    else:
        context.bot.send_message(chat_id=chat_id, text="You are already subscribed to feed updates.")


# Function to handle the /unsubscribe command
def unsubscribe(update, context):
    chat_id = update.message.chat_id
    if chat_id in subscribers:
        del subscribers[chat_id]
        context.bot.send_message(chat_id=chat_id, text="You have unsubscribed from feed updates.")
        save_subscribers(subscribers)


# Function to allow user preferred frequency
def set_frequency(update, context):
    chat_id = update.message.chat_id
    frequency = context.args[0] if context.args else None  # get frequency value from user or set to None if not provided

    frequency_options = {
        '1': 'Default (1 article per day)',
        '2': 'Regularly (2 articles per day)',
        '3': 'Informative (3 articles per day)'
    }

    if not frequency:
        # Show frequency options to the user
        options = [
            [InlineKeyboardButton(option, callback_data=option)] for option in frequency_options.values()
        ]
        reply_markup = InlineKeyboardMarkup(options)
        context.bot.send_message(chat_id=chat_id, text='Choose your preferred frequency:', reply_markup=reply_markup)
    elif frequency in frequency_options:
        # Load preferences
        preferences = load_preferences()

        # Update frequency in the preferences dictionary using chatID as key
        preferences[chat_id] = frequency

        # Save the updated preferences to the file
        save_preferences(preferences)

        # Send confirmation message to the user
        message = f"Your frequency preference has been set to: {frequency_options[frequency]}"
        context.bot.send_message(chat_id=chat_id, text=message)
    else:
        message = "Invalid frequency option. Please choose a valid option."
        context.bot.send_message(chat_id=chat_id, text=message)


# Callback function to handle frequency option selection
def select_frequency_option(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    frequency_option = query.data

    frequency_options = {
        'Default (1 article per day)': '1',
        'Regularly (2 articles per day)': '2',
        'Informative (3 articles per day)': '3'
    }

    if frequency_option in frequency_options:
        frequency = frequency_options[frequency_option]

        # Load preferences
        preferences = load_preferences()

        # Assign the new frequency value to the preferences dictionary using chatID as key
        preferences[chat_id] = frequency

        # Save the updated preferences to the file
        save_preferences(preferences)

        # Send confirmation message to the user
        message = f"Your frequency preference has been set to: {frequency_option}"
        context.bot.send_message(chat_id=chat_id, text=message)
    else:
        message = "Invalid frequency option. Please choose a valid option."
        context.bot.send_message(chat_id=chat_id, text=message)


# Create a Telegram bot instance
bot = telegram.Bot(token=bot_token)

# Load subscribers from the json file
subscribers = load_subscribers()

# Create an Updater
updater = Updater(bot=bot, use_context=True)

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

# Register command handlers
dispatcher.add_handler(CommandHandler(['start', 'subscribe'], subscribe, pass_args=True))
dispatcher.add_handler(CommandHandler('unsubscribe', unsubscribe))
dispatcher.add_handler(CommandHandler('frequency', set_frequency, pass_args=True))

# Register callback handler for frequency options
dispatcher.add_handler(CallbackQueryHandler(select_frequency_option))

# Start the bot
updater.start_polling()

# Schedule the send_articles function to run at 09:00 local time every day
schedule.every().day.at(get_next_occurrence(7, 30).strftime("%H:%M")).do(send_articles)

# Schedule the get_latest_news function to run at 09:00 local time every day
schedule.every().day.at(get_next_occurrence(7, 51).strftime("%H:%M")).do(get_latest_news)

while True:
    schedule.run_pending()
    time.sleep(1) 

# Stop the bot gracefully
updater.stop()
