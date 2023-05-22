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
import csv

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
        
        
#Function to save sent articles to CSV file
def save_sent_articles(sent_articles):
    #Limit 10 articles
    if len(sent_articles) > 10:
        sent_articles = sent_articles[-10:]
    
    with open('sent.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['subscriber_id', 'article_date', 'article_title'])
        for article in sent_articles:
            writer.writerow(article) 
     
     
#Function to load sent articles from CSV file
def load_sent_articles():
    sent_articles = []
    try:
        with open('sent.csv', 'r', newline='') as file:
            reader = csv.reader(file)
            next(reader)  # Skip header row
            for row in reader:
                subscriber_id, article_date, article_title = row
                sent_articles.append((subscriber_id, article_date, article_title))
    except FileNotFoundError:
        pass
    return sent_articles


#Function to check if an article has already been sent to a subscriber
def is_article_sent(subscriber_id, article_title):
    sent_articles = load_sent_articles()
    for article in sent_articles:
        if article[0] == subscriber_id and article[2] == article_title:
            return True
    return False

# Function to send articles to subscribers based on frequency preference
def send_articles():
    # Fetch and parse the RSS feed
    feed = feedparser.parse(feed_url)

    # Load preferences and subscribers
    preferences = load_preferences()
    subscribers = load_subscribers()

    # Load sent articles
    sent_articles = load_sent_articles()

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

                # Check if the article has already been sent to the subscriber
                if is_article_sent(chat_id, title):
                    # Skip sending this article, move to the next one
                    continue

                # Send the article to the subscriber
                message = f"{title}\n{description}\n{link}"
                bot.send_message(chat_id=chat_id, text=message)

                # Update the number of articles sent per day for the user
                articles_sent_per_day[chat_id] = articles_sent_per_day.get(chat_id, 0) + 1

                # Add the sent article to the list
                sent_articles.append((chat_id, formatted_date, title))
                save_sent_articles(sent_articles)

                # Check if the maximum number of articles per day has been sent for the user
                if articles_sent_per_day[chat_id] >= num_articles:
                    break  # Break out of the loop after reaching the maximum articles per day

    # Reset the count of articles sent per day for each user
    articles_sent_per_day.clear()

            

                 
# Function to handle the /subscribe command
def subscribe(update, context):
    chat_id = update.message.chat_id
    if chat_id not in subscribers:
        subscribers[chat_id] = None  # Update chatID of new subscriber
        context.bot.send_message(chat_id=chat_id,
                                 text="You have subscribed to feed updates. To continue, Choose the frequency of articles per day via the /frequency command.")
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
        '2': 'Regularly (Up to 2 articles per day)',
        '3': 'Informative (Up to 3 articles per day)'
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
#schedule.every().day.at(get_next_occurrence(7, 51).strftime("%H:%M")).do(get_latest_news)

while True:
    send_articles()
    time.sleep(10) 

# Stop the bot gracefully
updater.stop()
