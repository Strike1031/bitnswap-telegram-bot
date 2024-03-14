# Telegram Bot using Django
import sys
import time
from collections import defaultdict
import os
from dotenv import load_dotenv

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

# Initialize scheduler
scheduler = AsyncIOScheduler()

# SET Variables
load_dotenv()



# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# File path
FILE_PATH = 'file/report.xlsx'

TELEGRAM_BOT_TOKEN = os.environ.get('BOT_TOKEN')
# Dictionary to store user scores
class User_information:
    def __init__(self, user_id, user_name, user_score, user_login_timestamp):
        self.user_id = user_id
        self.user_name = user_name
        self.user_score = user_score
        self.user_login_timestamp = user_login_timestamp

users = defaultdict(User_information)

# Session time out seconds
session_time_out = 5 # 5 seconds

@sync_to_async
def post_person(user):
    models.Person(
        tg_id=user.id,
        tg_username=user.username,
        tg_fullname=user.full_name,
        arrived_at=get_time(),
    ).save()

@sync_to_async
def put_person(user, user_id):
    models.Person.objects.select_related().filter(pk=user_id, tg_id=user.id).update(left_at=get_time())

@sync_to_async
def get_last_id(user):
    last_id = models.Person.objects.select_related() \
        .filter(tg_id=user.id, left_at=None).values_list("pk", flat=True).last()
    active_id = models.Person.objects.select_related() \
        .filter(tg_id=user.id).values_list("pk", flat=True).last()
    if last_id >= active_id:
        return last_id
    else:
        return False


@sync_to_async
def get_data():
    persons = models.Person.objects.all()
    serializer = serializers.PersonSerializer(persons, many=True)

    all_data = []
    for i in range(0, len(serializer.data)):
        data = [serializer.data[i]['tg_fullname'], serializer.data[i]['arrived_at'], serializer.data[i]['left_at']]
        all_data.append(data)

    return all_data


def set_data(info):
    pandas.DataFrame(data=info, columns=['name', 'arrived', 'left']).to_excel(FILE_PATH)
    return 1


def get_time():
    current_time = datetime.now(pytz.timezone(settings.TIME_ZONE))
    return current_time.strftime('%Y-%m-%d %H:%M:%S')


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Get user that sent /start and log his name
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
    if user_id in users and (datetime.now() - users[user_id].user_login_timestamp).total_seconds() >= session_time_out:
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
    if user_id in users and (datetime.now() - users[user_id.user_login_timestamp]).total_seconds() >= session_time_out:
        await query.message.delete()
        await query._bot.send_message(chat_id, f"{user_name}, Verification successful. You can continue chatting.")
        # await query.message.reply_text(f"{user_name}, Verification successful. You can continue chatting.")
        users[user_id].user_login_timestamp = datetime.now()
    else:
        await query.message.delete()
        await query._bot.send_message(chat_id, f"{user_name}, Verification failed. Please try again.")

def set_user_score(user_id, user_name):
    users[user_id].user_id = user_id
    users[user_id].user_name = user_name
    if (user_id in users):
        users[user_id].user_score += 1
    else:
        users[user_id].user_score = 1
    users[user_id].user_login_timestamp = datetime.now()

# Function to update user score when a message is sent
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = -1
    user_name = ""
    if update.message.reply_to_message: # relying user
        user_id = update.message.reply_to_message.from_user.id
        user_name = update.message.reply_to_message.from_user.name
        print('----original--sender--name--', user_name)
    else:
        user_id = update.effective_user.id # normal user
        user_name = update.effective_user.name
        print('---sender--name--', user_name)

    if user_id in users:
        if (datetime.now() - users[user_id].user_login_timestamp).total_seconds() >= session_time_out:
            keyboard = [
                [InlineKeyboardButton("Verify", callback_data='verify')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"{user_name}, please click the button to verify that you're not a bot.", reply_markup=reply_markup)
        else:
            set_user_score(user_id, user_name)
    else:
        users[user_id] = User_information(user_id, user_name, 0, datetime.now())
        set_user_score(user_id, user_name)

# Function to calculate user rankings
async def calculate_rankings():
    # Add your ranking calculation logic here
    pass

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.name
    print("show_profile-------")
    if (user_id in users):
        pass
    else:
        users[user_id] = User_information(user_id, user_name, 0, datetime.now() - timedelta(seconds=session_time_out+10))
    # print profile of this user - users[user_id]
    print("this user--------", users[user_id].user_name)
    print("this user--------", users[user_id].user_score)
    
command_info = [
    BotCommand("start", "Start the bot"),
    BotCommand("profile", "Show user's profile"),
]

    
def main():
    # Add new job to scheduler to calculate rankings periodically
    scheduler.add_job(calculate_rankings, 'interval', hours=1)
    """Run the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    # await application.bot.set_my_commands(command_info)
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler),
            # CommandHandler("verify", verify_user),
            CommandHandler("profile", show_profile),
            CallbackQueryHandler(handle_verification, pattern='^verify$'),
        ],
        states={
        },
        fallbacks=[CommandHandler("start", start),  

        ],
    )

    application.add_handler(conv_handler)
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    
if __name__ == "__main__":
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Create a new event loop to ensure a clean start
    main()
