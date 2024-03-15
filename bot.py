# Telegram Bot using Django for ONT_coin
import sys
import time
from collections import defaultdict
import os
from dotenv import load_dotenv
import re

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


sys.dont_write_bytecode = True

import django
django.setup()
from app import models, serializers
from asgiref.sync import sync_to_async

import logging
from datetime import datetime, timedelta
import pytz
from config import settings
import pandas
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    BotCommand,
)
from telegram.constants import ParseMode
from telegram.ext._utils.types import BT
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    
)
import platform
import asyncio

from datetime import timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Initialize scheduler
scheduler = AsyncIOScheduler(timezone=pytz.timezone(settings.TIME_ZONE))

# SET Variables
load_dotenv()



# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Information structure for the user
class User_information:
    def __init__(self, user_id, user_name, user_score, user_login_timestamp):
        self.user_id = user_id
        self.user_name = user_name
        self.user_score = user_score
        self.user_login_timestamp = user_login_timestamp

# Array of user information - Important variable
# users = defaultdict(User_information)
users = {}
group_chat_id = 0
"""
    Main Initial variables
"""

# Session time out seconds
session_time_out = 10 * 60 # 10 minutes after, user login expires and he must verify by clicking the button to continue chat.
TELEGRAM_BOT_TOKEN = os.environ.get('BOT_TOKEN') # Bot token
# File path
FILE_PATH = 'file/report.xlsx'

"""
    Functions
"""

@sync_to_async
def save_users_to_database():
    for user_id, user_info in users.items():
        models.UserInfo.objects.update_or_create(
            user_id=user_info.user_id,
            defaults={
                'user_name': user_info.user_name,
                'user_score': user_info.user_score,
                'user_login_timestamp': user_info.user_login_timestamp
            }
        )

async def load_users_from_database():
    user_infos = await sync_to_async(list)(models.UserInfo.objects.all())
    for user_info in user_infos:
        users[int(user_info.user_id)] = User_information(
            user_id=int(user_info.user_id),
            user_name=user_info.user_name,
            user_score=user_info.user_score,
            user_login_timestamp=user_info.user_login_timestamp
        )

@sync_to_async
def get_data():
    persons = models.UserInfo.objects.all()
    serializer = serializers.PersonSerializer(persons, many=True)

    all_data = []
    for i in range(0, len(serializer.data)):
        data = [serializer.data[i]['user_id'], serializer.data[i]['user_name'], serializer.data[i]['user_score'], serializer.data[i]['user_login_timestamp']]
        all_data.append(data)

    return all_data


def set_data(info):
    pandas.DataFrame(data=info, columns=['user_id', 'user_name', 'user_score', 'user_login_timestamp']).to_excel(FILE_PATH)
    return 1


def get_time():
    current_time = datetime.now(pytz.timezone(settings.TIME_ZONE))
    return current_time.strftime('%Y-%m-%d %H:%M:%S')


async def report_to_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_data = await get_data()

    if set_data(active_data):
        await update.message.reply_document(
            document=open(FILE_PATH, 'rb'),
            filename='report.xlsx',
            caption='Report'
        )

    time.sleep(2)
    os.remove(FILE_PATH)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send message on `/start`."""
    user = update.effective_user
    logger.info("User %s started the conversation.", user.username)

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns `ConversationHandler.END`, which tells the
    ConversationHandler that the conversation is over.
    """
    return ConversationHandler.END

# Command to handle user verification button
async def verify_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_name = update.effective_user.name
    if user_id in users and (datetime.now(pytz.timezone(settings.TIME_ZONE)) - users[user_id].user_login_timestamp).total_seconds() >= session_time_out:
        keyboard = [
            [InlineKeyboardButton("Verify", callback_data='verify')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"{user_name}, please click the button to verify that you're not a bot.", reply_markup=reply_markup)
            
# Callback to handle user verification
async def handle_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    user_name = update.effective_user.name
    query = update.callback_query
    chat_id = query.message.chat_id  # This assumes the callback query is from a group chat
    if user_id in users and (datetime.now(pytz.timezone(settings.TIME_ZONE)) - users[user_id].user_login_timestamp).total_seconds() >= session_time_out:
        await query.message.delete()
        await query._bot.send_message(chat_id, f"{user_name}, Verification succeed to continue chatting")
        users[user_id].user_login_timestamp = datetime.now(pytz.timezone(settings.TIME_ZONE))
    else:
        await query.message.delete()
        await query._bot.send_message(chat_id, f"{user_name}, Verification failed. Please try again.")

# Function to update user score when a message is sent
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global group_chat_id
    if update.message.reply_to_message: # when the user reply one's message
        user_id = update.message.reply_to_message.from_user.id # original user
        user_name = update.message.reply_to_message.from_user.name
        reply_user_id = update.effective_user.id # replied user
        reply_user_name = update.effective_user.name
        chat_id = update.message.chat_id
        group_chat_id =  chat_id # necessary group id for scheduler handle globally
        if reply_user_id in users:
            if (datetime.now(pytz.timezone(settings.TIME_ZONE))- users[reply_user_id].user_login_timestamp).total_seconds() >= session_time_out:
                keyboard = [
                    [InlineKeyboardButton("Verify", callback_data='verify')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_to_message.delete()
                await update._bot.sendMessage(chat_id, f"{reply_user_name}, please click the button to verify that you're not a bot.", reply_markup=reply_markup)
            else:
                users[reply_user_id].user_score += 1
        else:
            users[reply_user_id] = User_information(reply_user_id, reply_user_name, 1, datetime.now(pytz.timezone(settings.TIME_ZONE)))
            
        users[user_id].user_score += 1
        
    else: # normal user when user only send a message
        user_id = update.effective_user.id 
        user_name = update.effective_user.name
        chat_id = update.message.chat_id
        group_chat_id =  chat_id # necessary group id for scheduler handle globally
        if user_id in users:
            if (datetime.now(pytz.timezone(settings.TIME_ZONE)) - users[user_id].user_login_timestamp).total_seconds() >= session_time_out:
                keyboard = [
                    [InlineKeyboardButton("Verify", callback_data='verify')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.delete()
                await update._bot.sendMessage(chat_id, f"{user_name}, please click the button to verify that you're not a bot.", reply_markup=reply_markup)
            else:
                users[user_id].user_score += 1
        else:
            users[user_id] = User_information(user_id, user_name, 1, datetime.now(pytz.timezone(settings.TIME_ZONE)))

async def reset_user_scores():
    global users
    for user in users.values():
        user.user_score = 0
        
#  reward Function
async def give_reward(bot: BT):
    # Sort users by score and get 3 top players
    top_players = sorted(users.values(), key=lambda x: x.user_score, reverse=True)[:3]
    # Format top players information
    top_players_info = "\n".join([f"{i+1}. {player.user_name}: 🪙 {player.user_score}" for i, player in enumerate(top_players)])
    full_message = f"Today's 🏆 top 3 players with rewards:\n\n{top_players_info}"
    # group_chat_id # necessary group id for scheduler handle globally
    if group_chat_id != 0:
        await bot.sendMessage(chat_id=group_chat_id, text=full_message, parse_mode=ParseMode.HTML)
    # Make all user's daily score 0 at this time -- this is new day!
    await reset_user_scores()

# /profile command
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.name
    # If user_id not in users, then set default
    if user_id not in users:
        print('-----------------------stress-----------------\n\n')
        users[user_id] = User_information(user_id, user_name, 0, datetime.now(pytz.timezone(settings.TIME_ZONE)) - timedelta(seconds=session_time_out+10))
    # display profile of this user - users[user_id]
    user_score = users[user_id].user_score
    # Calculate rank by comparing scores
    rank = 1 + sum(1 for user in users.values() if user.user_score > user_score)
     # Sort users by score and get  top 3 players
    sorted_users = sorted(set(users.values()), key=lambda x: (-x.user_score, x.user_id))        
    top_players = sorted_users[:3] # Get top 3 unique players based on score and then user_id
    # Format top players information
    top_players_info = '\n'.join([f"{i+1}. {player.user_name}: 🪙 {player.user_score}" for i, player in enumerate(top_players)])
    # send reply html
    await update.message.reply_html(text=f"{user_name} profile \n \
    🏆 Rank: {rank} \n \
    🪙 Score: {users[user_id].user_score} \n\n\n \
    Top 3 Players:\n{top_players_info} \n\n \
    ")

async def display_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(text=f" Welcome to our vibrant community! \n\n \
    Here, every message you post earns you points. \n \
    When another member responds to your post, you'll gain additional points, increasing your score. \n \
    Every day, at midnight (UTC+0), we celebrate by awarding rewards to the 🏆 top 3 users with the highest 🪙 scores. \n\n \
    Join us daily for challenges and 😊enjoy the camaraderie!  \n \
    ")
    
def main() -> None:
    # Load all user's data from the database
    """Run the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add new job to scheduler to save user data to database every 1 hour to prevent losing data
    scheduler.add_job(save_users_to_database, 'interval', hours=1)
    
    # Schedule the daily rewards function ( 00:00:00 UTC Every day, bot give rewards)
    scheduler.add_job(
        give_reward, 
        trigger=CronTrigger(hour=0, minute=0, second=0, timezone=pytz.timezone(settings.TIME_ZONE)), 
        args=[application.bot],
        name="daily_rewards"
    )

    # Start scheduler
    scheduler.start()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler),
            # CommandHandler("verify", verify_user),
            CommandHandler("report", report_to_excel),
            CommandHandler("profile", show_profile),
            CommandHandler("info", display_info),
            CallbackQueryHandler(handle_verification, pattern='^verify$'),
        ],
        states={
        },
        fallbacks=[CommandHandler("start", start),  

        ],
    )

    application.add_handler(conv_handler)
    # Run the bot until the user presses Ctrl-C
    # Run application and webserver together
    application.run_polling(allowed_updates=Update.ALL_TYPES)

        
if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    loop = asyncio.get_event_loop()
    loop.run_until_complete(load_users_from_database())  # load data from database
    loop.run_until_complete(main())  # main function
