import time
import requests
import feedparser
import concurrent.futures
from bs4 import BeautifulSoup
from openai import OpenAI
from telegram import Bot
from PIL import Image
from io import BytesIO
import sqlite3
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os


# Logging setup
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=LOG_LEVEL.upper(), format='%(asctime)s - %(levelname)s - %(message)s')

# Load variables from .env
load_dotenv()

# Reading the list of RSS feeds from .env
RSS_FEEDS = os.getenv("RSS_FEEDS", "").split(",")  # Comma-separated list

# Reading variables from .env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # API key OpenAI
TELEGRAM_BOT_API_KEY = os.getenv("TELEGRAM_BOT_API_KEY")  # API key Telegram
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")  # ID channel Telegram
DB_FILE = os.getenv("DB_FILE")  # Database file
# Read the prompts from the .env
filter_prompt = os.getenv("OPENAI_FILTER_PROMPT", "Default filter prompt for technology articles")
summary_prompt = os.getenv("OPENAI_SUMMARY_PROMPT", "Default summary prompt for Telegram")

# Creating clients for OpenAI and Telegram
openai_client = OpenAI(api_key=OPENAI_API_KEY)
telegram_bot = Bot(token=TELEGRAM_BOT_API_KEY)


def ensure_database_exists():
    """
    Checks the structure of the articles table, creates it if necessary.
    """
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        cursor = conn.cursor()
        # Checking the table structure
        cursor.execute("PRAGMA table_info(articles);")
        columns = [row[1] for row in cursor.fetchall()]

        required_columns = {'id', 'link', 'title', 'keywords', 'telegram_link', 'datetime'}
        if not required_columns.issubset(set(columns)):
            logging.info(f"Columns are missing in the articles table. Recreating the table.")
            setup_database()

        else:
            logging.info("The database structure has been checked. Everything is in order.")


def setup_database():
    """Creates a table with all the required fields if it doesn't already exist."""
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        cursor = conn.cursor()

        # Create table articles with all fields at once
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                link TEXT UNIQUE,
                title TEXT,
                keywords TEXT,
                telegram_link TEXT,
                datetime TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        logging.info("The database and the `articles` table have been successfully configured.")


def cleanup_old_articles():
    """
    Removes articles older than a week from the database.
    """
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        cursor = conn.cursor()

        # Calculate the cutoff date (1 week)
        cutoff_date = datetime.now() - timedelta(days=7)  # 1 week ago

        # Delete old articles
        cursor.execute('DELETE FROM articles WHERE datetime < ?', (cutoff_date,))
        conn.commit()
    logging.info("Old articles (older than 1 week) have been successfully deleted.")


def save_article_to_db(link, title, keywords, telegram_link=None):
    """
    Saves the article data to the database.
    """

    with sqlite3.connect(DB_FILE, timeout=10) as conn:  # Use with to autoclose the connection
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO articles (link, title, keywords, telegram_link, datetime) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)',
                (link, title, keywords, telegram_link)
            )
            conn.commit()  # commit should also remain in the with block
            logging.info(f"The article has been successfully added to the database: {link}")
        except sqlite3.IntegrityError:
            logging.info(f"The article already exists in the database: {link}")  # Changed from printing to logging


def clean_html(html):
    """Cleans HTML code by removing unnecessary tags.

    Args:
        html (str): The raw HTML content.

    Returns:
        str: Cleaned plain text from the HTML.
    """

    def parse_html(html):
        try:
            # Use “lxml” instead of the less optimal “html.parser”
            soup = BeautifulSoup(html, 'lxml')
            for tag in soup(["script", "style", "meta", "noscript"]):
                tag.extract()
            text = soup.get_text(separator="\n")
            return "\n".join(line.strip() for line in text.splitlines() if line.strip())
        except Exception as e:
            logging.info(f"HTML processing error: {e}")
            return ""

    # We limit the execution time - a timeout of 5 seconds.
    with (concurrent.futures.ThreadPoolExecutor() as executor):
        future = executor.submit(parse_html, html)
        try:
            return future.result(timeout=5)
        except concurrent.futures.TimeoutError:
            logging.info("The HTML processing took way too long! Skipping...")
            return ""


def filter_article(cleaned_text, link):
    prompt = filter_prompt.format(article_text=cleaned_text[:3000])
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        answer = response.choices[0].message.content.strip().lower()

        logging.info(f"Processing link: {link}")
        logging.info(f"ChatGPT desicion: {answer}")

        return answer.lower() == "yes"

    except Exception as e:
        logging.error(f"Decision error on passing the filter through OpenAI: {e}")
        return None


def is_title_similar_with_chatgpt(new_title, existing_titles):
    """
    Checks the similarity of a new header to existing headers
    in the database using a GPT query.
    """
    # Merge existing headers in a readable format
    formatted_existing_titles = "\n".join(f"- {title}" for title in existing_titles)

    # Creating a common prompt for GPT
    prompt = f"""
    Check if the following new title is too similar to any of the existing titles.
    
    New title:
    "{new_title}"

    Existing titles:
    {formatted_existing_titles}
    
    Answer "Yes" if the new title is too similar to any of the existing titles. 
    Otherwise, answer "No".
    
    ONLY reply with "Yes" or "No".
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        decision = response.choices[0].message.content.strip().lower()

        logging.info(f"GPT decision for title similarity check: {decision}")

        return decision == "yes"

    except Exception as e:
        logging.error(f"Error comparing headers via OpenAI: {e}")
        return None


def extract_main_image(html):
    """
    Extracts the main article image based on OpenGraph (<meta property=“og:image”>),
    checks its availability and resolution.
    """
    try:
        soup = BeautifulSoup(html, 'lxml')

        # Finding a picture using OpenGraph
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            image_url = og_image["content"]

            # Check if the image is available and its size
            response = requests.get(image_url, timeout=5)
            if response.status_code == 200:
                # Check the MIME type (e.g., support only images)
                content_type = response.headers.get('Content-Type', '')
                if content_type.startswith('image/'):
                    # Checking the image resolution
                    image = Image.open(BytesIO(response.content))
                    width, height = image.size
                    if width >= 300 and height >= 300:  # Minimum resolution
                        return image_url
                    else:
                        logging.info(f"The image is too small: {width}x{height}px")
            else:
                logging.error(f"Failed to load the image: {image_url}")
    except Exception as e:
        logging.error(f"Image extraction error: {e}")
    return None


def generate_content(cleaned_text, link):
    if not cleaned_text.strip():
        logging.info(f"Blank text for content: {link} - skipping.")
        return None  # Skip the empty text
    prompt = summary_prompt.format(article_text=cleaned_text, article_link=link)

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        gpt_article = response.choices[0].message.content.strip()
        return gpt_article  # Successfully completed - return the result
    except Exception as e:
        logging.error(f"Error generating content via OpenAI: {e}")
        return None  # If an error occurred, return None


def publish_to_telegram(post, photo_url=None):
    for attempt in range(3):  # Try three times
        try:
            if photo_url:
                message = telegram_bot.send_photo(chat_id=CHANNEL_ID, photo=photo_url, caption=post, parse_mode="HTML", timeout=10)
            else:
                message = telegram_bot.send_message(chat_id=CHANNEL_ID, text=post, parse_mode="HTML", timeout=10)
            telegram_message_link = f"https://t.me/{CHANNEL_ID.replace('-', '')}/{message.message_id}"
            logging.info("The article was published on Telegram. Link to post: {}".format(telegram_message_link))
            return telegram_message_link
        except Exception as e:
            logging.error(f"Error when publishing to Telegram on an attempt to {attempt + 1}: {e}")
            time.sleep(5)  # Waiting for the next attempt
    return None


def process_rss_feed(feed_url):
    """
    Processes RSS feed, selects articles, checks them and publishes them to Telegram.
    """
    feed = feedparser.parse(feed_url)
    logging.info(f"Downloaded articles from RSS feed {feed_url}: {len(feed.entries)}")

    # Load existing headers from the database once
    with sqlite3.connect(DB_FILE, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT title FROM articles ORDER BY datetime DESC LIMIT 30')
        existing_titles = [row[0] for row in cursor.fetchall()]

    for entry in feed.entries:
        try:
            link = entry.link
            new_title = entry.title

            # Check for doubles at the link
            with sqlite3.connect(DB_FILE, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT 1 FROM articles WHERE link = ?', (link,))
                already_exists = cursor.fetchone()

            if already_exists:
                logging.info(f"The article has already been processed and is in the database, I skip it: {link}")
                continue

            # Checking the uniqueness of a new header
            if is_title_similar_with_chatgpt(new_title, existing_titles):
                logging.info(f"The header is too similar to existing headers. Skip: {new_title}")
                continue

            # Main process: article processing
            response = requests.get(link, timeout=10)
            html = response.text
            cleaned_text = clean_html(html)

            if not filter_article(cleaned_text, link):  # Filtering the article
                logging.info(f"The filter rejected the article: {link}")
                continue

            post = generate_content(cleaned_text, link)
            if not post:
                logging.info(f"Error generating content for an article: {link}")
                continue

            # Checking the main image
            photo_url = extract_main_image(html)
            telegram_link = publish_to_telegram(post, photo_url)

            if telegram_link:  # Only if the publication is successful
                save_article_to_db(link, new_title, cleaned_text, telegram_link)

        except Exception as e:
            logging.info(f"Article processing error {entry.link}: {e}")


def wait_until_next_hour():
    """Waiting until the next 00 minutes of the next hour."""
    now = datetime.now()
    # The time of the next hour
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    # Calculating how many seconds to wait
    wait_time = (next_hour - now).total_seconds()
    logging.info(f"Waiting {wait_time} seconds for the next full hour ({next_hour}).")
    time.sleep(wait_time)


def main():
    # We wait until 00 minutes past the next hour
    wait_until_next_hour()

    while True:
        try:
            logging.info("Starting to process RSS feeds...")
            for feed_url in RSS_FEEDS:
                process_rss_feed(feed_url)

            cleanup_old_articles()  # Clearing old data before waiting

            logging.info("Waiting for the next full hour...")
            wait_until_next_hour()  # We wait until the beginning of the next hour
        except Exception as e:
            logging.info(f"Error in the main loop: {e}")


if __name__ == "__main__":
    ensure_database_exists()  # Making sure the database exists
    main()
