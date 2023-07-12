import cv2
import csv
import datetime
import os
import pandas as pd
import json
import time
from urllib.parse import urljoin
import snscrape.modules.twitter as sntwitter
import feedparser
import pytz
import requests
import schedule
import telegram
import threading
import virustotal_python
from dotenv import load_dotenv
from base64 import urlsafe_b64encode
from bs4 import BeautifulSoup
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, Filters
import requests

load_dotenv('api.env')
current_date = datetime.datetime.now()
formatted_date = current_date.strftime("%d %B %Y")
formatted_date_1 = current_date.strftime("%Y-%m-%d")

# Replace 'YOUR_BOT_TOKEN' with the token provided by BotFather
bot_token = os.getenv("BOT_TOKEN")

# Replace 'FEED_URL' with the actual RSS feed URL
feed_url = 'https://www.bleepingcomputer.com/feed/'

# Define the filename for the CSV file
filename = 'sent.csv'

FREQUENCY, PROFILE = range(2)
PROFILE_CONFIRMATION = 2
report_url_calls = 0
report_url_last_called = 0


def uploadToDocker(update, context):
    chat_id = update.message.chat_id

    if update.message.photo:
        # Handle compressed photo
        image_file = context.bot.getFile(update.message.photo[-1].file_id)
        image_url = 'http://172.17.0.2:5000/upload'  # Replace with your Docker Flask endpoint

        with requests.get(image_file.file_path) as response:
            response.raise_for_status()
            image_data = response.content
            
        image_size = len(image_data)
        context.bot.send_message(chat_id=chat_id, text=f"Image size (compressed): {image_size}")

        # Send the image file to the Docker Flask app
        files = {'image': image_data}
        response = requests.post(image_url, files=files)

        if response.status_code == 200:
            message = "Image uploaded successfully to the Docker container."
            context.bot.send_message(chat_id=chat_id, text=message)

            # Receive the image file from the Docker Flask app
            response = requests.get(image_url)

            if response.status_code == 200:
                with open('received_image.jpg', 'wb') as f:
                    f.write(response.content)
                message = "Image received successfully from Docker container."
                context.bot.send_message(chat_id=chat_id, text=message)
                
                scan_qr(update, context)

            else:
                message = "Failed to receive the image from the Docker container."
                context.bot.send_message(chat_id=chat_id, text=message)

        else:
            message = "Failed to upload image to the Docker container."
            context.bot.send_message(chat_id=chat_id, text=message)

    elif update.message.document and 'image' in update.message.document.mime_type:
        #Handle uncompressed image file
        image_file = context.bot.getFile(update.message.document.file_id)
        image_url = 'http://172.17.0.2:5000/upload'  

        with requests.get(image_file.file_path) as response:
            response.raise_for_status()
            image_data = response.content
            
        image_size = len(image_data)
        context.bot.send_message(chat_id=chat_id, text=f"Image size (uncompressed): {image_size}")

        # Send the image file to the Docker Flask app
        files = {'image': image_data}
        response = requests.post(image_url, files=files)

        if response.status_code == 200:
            message = "Image uploaded successfully to the Docker container."
            context.bot.send_message(chat_id=chat_id, text=message)

            # Receive the image file from the Docker Flask app
            response = requests.get(image_url)

            if response.status_code == 200:
                with open('received_image.jpg', 'wb') as f:
                    f.write(response.content)
                message = "Image received successfully from Docker container."
                context.bot.send_message(chat_id=chat_id, text=message)
                
                scan_qr(update, context)

            else:
                message = "Failed to receive the image from the Docker container."
                context.bot.send_message(chat_id=chat_id, text=message)

        else:
            message = "Failed to upload image to the Docker container."
            context.bot.send_message(chat_id=chat_id, text=message)

    else:
        message = "Please upload an image or document."
        context.bot.send_message(chat_id=chat_id, text=message)

def scan_qr(update, context):
    chat_id = update.message.chat_id
    if update.message.photo:
        image_file = context.bot.getFile(update.message.photo[-1].file_id)
    elif update.message.document and 'image' in update.message.document.mime_type:
        image_file = context.bot.getFile(update.message.document.file_id)
    else:
        message = "Please upload an image."
        context.bot.send_message(chat_id=chat_id, text=message)
        return

    image_path = 'received_image.jpg'
    image_file.download(image_path)

    # Perform QR code detection and malicious code checking
    img = cv2.imread(image_path)
    det = cv2.QRCodeDetector()
    try:
        val, pts, st_code = det.detectAndDecode(img)
        if val == "":
            response = "The image does not contain any QR codes"
        else:
            response = val
            context.bot.send_message(chat_id=chat_id, text=val)
            api_key = os.getenv("API_KEY")
            with virustotal_python.Virustotal(api_key) as vtotal:
                try:
                    # safe encode URL in base64 format
                    url_id = urlsafe_b64encode(response.encode()).decode().strip("=")

                    # Send the URL for analysis
                    resp = vtotal.request("urls", data={"url": response}, method="POST")
                    report = vtotal.request(f"urls/{url_id}")

                    # Check the scan results
                    if report.data["attributes"]["last_analysis_stats"]["malicious"] > 0:
                        message = f"The URL '{response}' is malicious."
                    else:
                        message = f"The URL '{response}' is safe."

                    context.bot.send_message(chat_id=chat_id, text=message)
                except virustotal_python.VirustotalError as err:
                    print(f"Failed to send URL '{response}' for analysis and get the report: {err}")
                    message = f"QR does not have a valid URL!"
                    context.bot.send_message(chat_id=chat_id, text=message)
    except Exception as e:
        response = "The image does not contain any QR codes"
        context.bot.send_message(chat_id=chat_id, text=str(e))
        
        
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


# Function to save sent articles to CSV file
def save_sent_articles(sent_articles):
    # Limit 10 articles
    if len(sent_articles) > 10:
        sent_articles = sent_articles[-10:]

    with open('sent.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['subscriber_id', 'article_date', 'article_title'])
        for article in sent_articles:
            writer.writerow(article)


def load_sent_articles(x):
    sent_articles = []
    try:
        with open('sent.csv', 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            # Skip header row
            next(reader)
            for row in reader:
                if x == 1:
                    subscriber_id, article_date, article_title = row
                    sent_articles.append((subscriber_id, article_date, article_title))
                elif x == 2:
                    if row[1] == str(current_date):
                        sent_articles.append(row[2])
                    else:
                        break
        return sent_articles
    except FileNotFoundError:
        return sent_articles


# Function to check if an article has already been sent to a subscriber
def is_article_sent(subscriber_id, article_title):
    sent_articles = load_sent_articles(1)
    for article in sent_articles:
        if article[0] == subscriber_id and article[2] == article_title:
            return True
    return False
    

def get_latest_news():
    base_url = 'https://www.csa.gov.sg/alerts-advisories'
    response = requests.get(base_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('a', class_='m-card-article')

    for article in articles:
        href = article.get('href')
        news_url = urljoin(base_url, href)
        response = requests.get(news_url)
        soup = BeautifulSoup(response.text, 'html.parser')

        #Extract date from published article
        note_text = soup.find('p', class_='m-card-article__note').text
        date = note_text.split('|')[0].strip()
        date = date.replace("Published on ", "")

        if date == formatted_date and news_url not in existing_content:
            #Checks if file exists
            file_exists = os.path.isfile(filename)
            with open(filename, 'a' if file_exists else 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                if not file_exists:
                    writer.writerow(['subscriber_id', 'article_date', 'article_title'])
                preferences = load_preferences()
                keys = preferences.keys()
                for key in keys:
                    writer.writerow([key, formatted_date_1, news_url])
                    message1 = "Latest Alert & Advisories: " + news_url
                    bot.send_message(chat_id=key, text=message1)
        else:
            print("Old news!")
            return
    
def get_latest_tweets():
    #Get the number of rows in the dataframe
    num_rows = int(tweets_df.shape[0]) - 1

    #Checks if file exists
    file_exists = os.path.isfile(filename)

    with open(filename, 'a' if file_exists else 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        if not file_exists:
            writer.writerow(['subscriber_id', 'article_date', 'article_title'])

        #Loop through each row in the dataframe and send it as a seperate message
        for i in range(0, num_rows):
            m = tweets_df.iloc[i]
            date_str = str(m[0])
            content = str(m[1])

            #Convert string to datetime object
            datetime_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S%z")
            date_only = datetime_obj.date()

            #Only sent today's tweet and those that have not been sent
            if date_only == current_date and content not in existing_content:
                preferences = load_preferences()
                keys = preferences.keys()
                for key in keys:
                    writer.writerow([key, date_only, content])
                    msg = str(date_only) + " " + content

                    bot.send_message(chat_id=key, text=msg)
            else:
                print("No new tweets!")
                return
                
                               
# Function to send articles to subscribers based on frequency preference
def send_articles():
    # Fetch and parse the RSS feed
    feed = feedparser.parse(feed_url)

    # Load preferences and subscribers
    preferences = load_preferences()
    subscribers = load_subscribers()

    # Load sent articles
    sent_articles = load_sent_articles(1)

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
        for chat_id, frequency_profile in preferences.items():
            frequency, profile = frequency_profile

            if frequency and chat_id and profile == "tech_savvy" in preferences:
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

# Function to scan a URL using VirusTotal API
def scan_url(update, context):
    api_key = os.getenv("API_KEY")
    chat_id = update.message.chat_id
    # Get user URL input
    url = context.args[0] if context.args else None

    if url:
        # Create a VirusTotal instance using the API key
        with virustotal_python.Virustotal(api_key) as vtotal:
            try:
                # safe encode URL in base64 format
                url_id = urlsafe_b64encode(url.encode()).decode().strip("=")

                # Send the URL for analysis
                resp = vtotal.request("urls", data={"url": url}, method="POST")
                report = vtotal.request(f"urls/{url_id}")

                # Check the scan results
                if report.data["attributes"]["last_analysis_stats"]["malicious"] > 0:
                    message = f"The URL '{url}' is malicious."
                else:
                    message = f"The URL '{url}' is safe."

                context.bot.send_message(chat_id=chat_id, text=message)
            except virustotal_python.VirustotalError as err:
                print(f"Failed to send URL '{url}' for analysis and get the report: {err}")
                message = f"Failed to scan the URL. Please try again later."
                context.bot.send_message(chat_id=chat_id, text=message)
    else:
        message = "Please provide a valid URL."
        context.bot.send_message(chat_id=chat_id, text=message)

def write_url_to_csv(url):
    fieldnames = ['Reported Link', 'Label']
    with open('toReview.csv', 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writerow({'Reported Link': url, 'Label': ''})

def rate_limit(limit, period):
    def decorator(func):
        def wrapper(*args, **kwargs):
            global report_url_calls
            global report_url_last_called

            now = time.time()
            elapsed_time = now - report_url_last_called

            if elapsed_time < period:
                if report_url_calls >= limit:
                    return  # Rate limit exceeded, do not execute the function

            # Execute the function
            result = func(*args, **kwargs)

            # Update rate limit variables
            report_url_calls += 1
            report_url_last_called = now

            return result
        return wrapper
    return decorator

# The actual report_url function
@rate_limit(limit=2, period=3600)  # 2 requests per 3600 seconds (1 hour)
def report_url(update, context):
    chat_id = update.message.chat_id
    url = context.args[0] if context.args else None

    if url:
        # Write the URL to the CSV file for manual review
        write_url_to_csv(url)

        message = f"URL '{url}' has been reported for manual review."
        context.bot.send_message(chat_id=chat_id, text=message)
    else:
        message = "Please provide a valid URL."
        context.bot.send_message(chat_id=chat_id, text=message)
  

# Function to handle the /subscribe command
def start(update, context):
    chat_id = update.message.chat_id
    preferences = load_preferences()

    if chat_id not in subscribers:
        subscribers[chat_id] = None  # Update chatID of new subscriber
        bot.send_message(chat_id=chat_id, text="Thank you for subscribing.\n\nTo scan a URL for malware using VirusTotal, use the /scanurl command followed by the URL.\n\nTo scan a potentially malicious URL from a QR code, upload the QR image file to this chat.\n\nUse the /unsubscribe command to unsubscribe from this bot.")
        save_subscribers(subscribers)
        
        profile_options = {
            'non_tech_savvy': 'Non-Tech-Savvy',
            'tech_savvy': 'Tech-Savvy'
        }

        options = [
            [InlineKeyboardButton(option, callback_data=key)] for key, option in profile_options.items()
        ]
        reply_markup = InlineKeyboardMarkup(options)
        update.message.reply_text("Choose your profile option:", reply_markup=reply_markup)
        return PROFILE
    else:
        bot.send_message(chat_id=chat_id, text="You are already subscribed to feed updates.")

    return ConversationHandler.END
    
    
    
# Function to handle the /unsubscribe command
def unsubscribe(update, context):
    chat_id = update.message.chat_id

    if chat_id in subscribers:
        del subscribers[chat_id]
        save_subscribers(subscribers)

    preferences = load_preferences()

    pref_chat_id = str(update.message.chat_id)

    if pref_chat_id in preferences:
        del preferences[pref_chat_id]
        save_preferences(preferences)

    context.bot.send_message(chat_id=chat_id, text="You have unsubscribed from feed updates.")

def select_option(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    option = context.user_data['option']

    if option == 'frequency':
        frequency_options = {
            '1': 'Default (1 article per day)',
            '2': 'Regularly (Up to 2 articles per day)',
            '3': 'Informative (Up to 3 articles per day)'
        }

        options = [
            [InlineKeyboardButton(key, callback_data=key)] for key in frequency_options.keys()
        ]
        reply_markup = InlineKeyboardMarkup(options)
        context.bot.send_message(chat_id=chat_id, text='Choose your preferred frequency:', reply_markup=reply_markup)
        return FREQUENCY

    return ConversationHandler.END

def profile(update, context):
    chat_id = update.effective_chat.id
    profile_options = {
    'non_tech_savvy': 'Non-Tech-Savvy',
    'tech_savvy': 'Tech-Savvy'}

    # Load preferences
    preferences = load_preferences()

    # Get the current profile
    current_profile = preferences.get(str(chat_id), [None, None])[1]

    # Determine the profile to switch to
    new_profile = 'non_tech_savvy' if current_profile == 'tech_savvy' else 'tech_savvy'

    # Display the current profile and prompt for confirmation
    message = f"Your current profile is: {profile_options[current_profile]}\n"
    message += f"Do you want to change to: {profile_options[new_profile]}?"

    # Prepare the inline keyboard with Yes and No options
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data='confirm')],
        [InlineKeyboardButton("No", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Send the message with the inline keyboard
    context.bot.send_message(chat_id=chat_id, text=message, reply_markup=reply_markup)

    # Store the new profile option in the context
    context.user_data['new_profile'] = new_profile

    return PROFILE_CONFIRMATION

def profile_confirmation(update, context):
    query = update.callback_query
    chat_id = query.message.chat_id
    confirmation = query.data
    profile_options = {
        'non_tech_savvy': 'Non-Tech-Savvy',
        'tech_savvy': 'Tech-Savvy'
    }

    if confirmation == 'confirm':
        new_profile = context.user_data['new_profile']

        # Load preferences
        preferences = load_preferences()

        # Update the profile preference
        preferences[str(chat_id)] = [preferences.get(str(chat_id), [None, None])[0], new_profile]

        # Clear the frequency preference if switching to non-tech savvy
        if new_profile == 'non_tech_savvy':
            preferences[str(chat_id)][0] = None
        else:
            preferences[str(chat_id)][1] = "tech_savvy"
            save_preferences(preferences)
            frequency_options = {
                '1': 'Default (1 article per day)',
                '2': 'Regularly (Up to 2 articles per day)',
                '3': 'Informative (Up to 3 articles per day)'
            }

            options = [
                [InlineKeyboardButton(option, callback_data=key)] for key, option in frequency_options.items()
            ]
            reply_markup = InlineKeyboardMarkup(options)
            context.bot.send_message(chat_id=chat_id, text='Choose your preferred frequency:', reply_markup=reply_markup)
            return FREQUENCY

        # Save the updated preferences to the file
        save_preferences(preferences)

        profile = profile_options[new_profile]
        message = f"Your profile has been updated to: {profile}"

        context.bot.send_message(chat_id=chat_id, text=message)
    elif confirmation == 'cancel':
        context.bot.send_message(chat_id=chat_id, text="Profile change cancelled.")

    return ConversationHandler.END

def select_frequency_option(update, context):
    query = update.callback_query
    chat_id = str(query.message.chat_id)  # Convert chat ID to a string
    frequency_option = query.data

    frequency_options = {
        '1': 'Default (1 article per day)',
        '2': 'Regularly (Up to 2 articles per day)',
        '3': 'Informative (Up to 3 articles per day)'
    }

    if frequency_option in frequency_options:
        frequency = frequency_option
        context.user_data['frequency'] = frequency

        # Load preferences
        preferences = load_preferences()

        # Update the frequency preference
        preferences[chat_id] = [frequency, preferences.get(chat_id, [None, None])[1]]

        # Save the updated preferences to the file
        save_preferences(preferences)

        message = f"Your frequency preference has been set to: {frequency_options[frequency_option]}\n\nYou can change your profile preference using /profile."
        context.bot.send_message(chat_id=chat_id, text=message)
    else:
        message = "Invalid frequency option. Please choose a valid option."
        context.bot.send_message(chat_id=chat_id, text=message)

    return ConversationHandler.END

def select_profile_option(update, context):
    query = update.callback_query
    chat_id = str(query.message.chat_id)  # Convert chat ID to a string
    profile_option = query.data

    profile_options = {
        'non_tech_savvy': 'Non-Tech-Savvy',
        'tech_savvy': 'Tech-Savvy'
    }

    if profile_option in profile_options:
        # Load preferences
        preferences = load_preferences()

        # Update the profile preference
        preferences[chat_id] = [preferences.get(chat_id, [None, None])[0], profile_option]

        # Save the updated preferences to the file
        save_preferences(preferences)

        profile = profile_options[profile_option]

        context.user_data['profile_option'] = profile_option
        context.user_data['option'] = 'frequency' if profile_option == 'tech_savvy' else 'profile'

        if profile_option == 'tech_savvy':
            frequency_options = {
                '1': 'Default (1 article per day)',
                '2': 'Regularly (Up to 2 articles per day)',
                '3': 'Informative (Up to 3 articles per day)'
            }

            options = [
                [InlineKeyboardButton(option, callback_data=key)] for key, option in frequency_options.items()
            ]
            reply_markup = InlineKeyboardMarkup(options)
            context.bot.send_message(chat_id=chat_id, text='Choose your preferred frequency:', reply_markup=reply_markup)
            return FREQUENCY
        else:
            # End the conversation handler here
            context.bot.send_message(chat_id=chat_id, text='Your profile option has been saved.\n\nYou can change your profile preference using /profile.')
            return ConversationHandler.END

    return ConversationHandler.END


def cancel(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Profile change cancelled.")
    return ConversationHandler.END
    
    
    
# Create a Telegram bot instance
bot = telegram.Bot(token=bot_token)

# Load subscribers from the json file
subscribers = load_subscribers()

# Create an Updater
updater = Updater(bot=bot, use_context=True)

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

#handle photo being uploaded to telegram chat
message_handler = MessageHandler(Filters.photo | Filters.document, uploadToDocker)

# Register command handlers
#dispatcher.add_handler(CommandHandler(['start', 'subscribe'], subscribe, pass_args=True))
dispatcher.add_handler(CommandHandler('unsubscribe', unsubscribe))
#dispatcher.add_handler(CommandHandler('frequency', set_frequency, pass_args=True))
#dispatcher.add_handler(CommandHandler('profile', set_profile, pass_args=True))
dispatcher.add_handler(CommandHandler('scanurl', scan_url, pass_args=True))
dispatcher.add_handler(CommandHandler('report', report_url, pass_args=True))
dispatcher.add_handler(message_handler)


conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start,pass_chat_data=True), CommandHandler('profile', profile, pass_chat_data=True)],
    states={
        FREQUENCY: [CallbackQueryHandler(select_frequency_option)],
        PROFILE: [CallbackQueryHandler(select_profile_option)],
        PROFILE_CONFIRMATION: [CallbackQueryHandler(profile_confirmation)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)


# Read the existing content from the CSV file
existing_content = load_sent_articles(2)

#option handler
updater.dispatcher.add_handler(conv_handler)

# Start the bot
updater.start_polling()

#Schedule the get_latest_news function to run every day
#schedule.every().day.at("01:00").do(get_latest_news)

#Schedule the get_latest_tweets function to run every day
#schedule.every().day.at("01:00").do(get_latest_tweets)

# Schedule the send_articles function to run every day
schedule.every().day.at("09:08").do(send_articles)


while True:
    schedule.run_pending()
    time.sleep(1)
    # Uncomment below for testing
    # send_articles()
    # time.sleep(10)

# Stop the bot gracefully
updater.stop()
