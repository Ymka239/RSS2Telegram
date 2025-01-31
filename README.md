# RSS2Telegram Bot

**RSS2Telegram Bot** is a Python-based automation tool designed to fetch, filter, and transform RSS feed articles into engaging Telegram posts. With its modular and flexible design, this bot can be easily adapted for use with different Telegram channels and RSS feeds.

---

## Features

- **Automated RSS Feed Processing**: Periodically fetches new articles from multiple RSS feeds.
- **AI-Powered Content Filtering**: Filters irrelevant or promotional articles using OpenAI GPT.
- **Engaging Content Creation**: Generates concise, captivating summaries for Telegram-friendly posts.
- **Automatic Telegram Publishing**: Posts articles to a specified Telegram channel, with optional article images.
- **Duplicate Prevention**: Maintains an SQLite database to track posted articles and avoid reposts. Includes logic to check duplication using both the database and OpenAI similarity checks.
- **Flexible Configuration**: Adjust feed sources, Telegram credentials, and database path via an `.env` file.

---

## Project Structure

```plaintext
├── rss2telegram_bot.py    # Main script with all logic
├── .env                   # Environment variables configuration (not committed to Git)
├── example.env            # Example `.env` file for configuration
├── articles.db            # SQLite database to prevent duplicate posts (auto-created)
├── articles.db            # SQLite database to track articles and prevent duplicate posts (auto-created). Contains columns like `id`, `link`, `title`, `keywords`, `telegram_link`, and `datetime`.
├── LICENSE                # License file
├── README.md              # Project overview (this file)
```

---

## Installation

Follow these steps to set up and run the **RSS2Telegram Bot**.

### Prerequisites

1. Python 3.8 or later installed on your system.
2. `pip` for managing Python package installations.
3. Active Telegram Bot credentials and channel ID.
4. [OpenAI API key](https://platform.openai.com/) for advanced filtering and content creation. Note that OpenAI API may have request limits or timeouts. The bot handles these scenarios gracefully by falling back to its default logic where necessary.

### Steps

1. **Clone the Repository**:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2. **Configure Environment Variables**:
    Copy the `example.env` file to `.env`:
    ```bash
    cp example.env .env
    ```
    Open the `.env` file and fill in the required fields:
    - List of RSS feed URLs.
    - Telegram API credentials.
    - OpenAI API key.
    - Absolute path to the database file.

3. **Install Dependencies**:
    Run the following command to install all required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

4. **Run the Bot**:
    Launch the bot script:
    ```bash
    python rss2telegram_bot.py
    ```

---

## Configuration

Configure all required details in the `.env` file.

### Essential Environment Variables

| Variable               | Required | Description                                                           |
|------------------------|----------|-----------------------------------------------------------------------|
| `RSS_FEEDS`            | Yes      | A comma-separated list of RSS feed URLs.                              |
| `TELEGRAM_BOT_API_KEY` | Yes      | Telegram bot API token obtained from @BotFather.                      |
| `TELEGRAM_CHANNEL_ID`  | Yes      | Telegram channel ID (e.g., `@channelname` or `-100...`).              |
| `OPENAI_API_KEY`       | Yes      | OpenAI API key for AI-driven features.                                |
| `DB_FILE`              | Yes      | Absolute path to the SQLite database file.                            |
| `LOG_LEVEL`            | No       | Log verbosity level, e.g., `DEBUG`, `INFO`, `ERROR`, or `WARNING`.    |
| `OPENAI_FILTER_PROMPT` | No       | Functional prompt for filtering articles.                             |
| `OPENAI_SUMMARY_PROMPT`| No       | Functional prompt for generating Telegram posts.                      |

The `example.env` file includes fully functional prompts for OpenAI filtering and content generation:
- `OPENAI_FILTER_PROMPT`: Default logic excludes promotional articles or unrelated topics. If not configured, a default filtering prompt is used by the bot.
- `OPENAI_SUMMARY_PROMPT`: Generates concise Telegram-friendly posts. If not provided, a default summary prompt is applied. These prompts are fully customizable for specific use cases.

Updated `.env` Example:
Example `.env` file:
```plaintext
RSS_FEEDS=https://example.com/rss,https://anotherexample.com/rss
TELEGRAM_BOT_API_KEY=your_telegram_bot_api_key
TELEGRAM_CHANNEL_ID=-1001234567890
OPENAI_API_KEY=your_openai_api_key
DB_FILE=/absolute/path/to/articles.db
OPENAI_FILTER_PROMPT="Default prompt for filtering RSS articles."
OPENAI_SUMMARY_PROMPT="Default summary for generating Telegram content."
LOG_LEVEL=INFO
```

## Running in Background

To run the bot continuously in the background, you can utilize the following methods:

- **Using `nohup`**:
    ```bash
    nohup python rss2telegram_bot.py &
    ```
    This ensures the bot runs in the background even if the terminal is closed.

- **Using Cron**:
    For automated startup during system reboots, add this to your cron jobs (`crontab -e`):
    ```bash
    @reboot python /absolute/path/to/rss2telegram_bot.py
    ```
    Replace `/absolute/path/to/rss2telegram_bot.py` with the correct script path.

- **Using `systemd`**:
    For advanced background management with automated restarts:
    Create `/etc/systemd/system/rss2telegram_bot.service`:
    ```bash
    [Unit]
    Description=RSS2Telegram Bot Service
    After=network.target

    [Service]
    ExecStart=/usr/bin/python3 /absolute/path/to/rss2telegram_bot.py
    Restart=on-failure
    RestartSec=5s
    User=<your_username>

    [Install]
    WantedBy=multi-user.target
    ```
    Replace `/absolute/path/to/rss2telegram_bot.py` and `<your_username>` as necessary. Enable and start with:
    ```bash
    sudo systemctl enable rss2telegram_bot.service
    sudo systemctl start rss2telegram_bot.service
    ```

## How It Works

- **Duplicate Prevention**: Before posting, the bot checks the database for existing articles based on their `link`. In addition, OpenAI API is used to detect semantic similarity using the `is_title_similar_with_chatgpt` function to reduce near-duplicate content.

1. The bot periodically fetches article links and metadata from RSS feeds specified in the `.env` file.
2. Articles are filtered using OpenAI GPT to ensure they are appropriate for publication and meet the desired criteria.
3. Approved articles are processed to generate brief, engaging summaries (complete with hashtags), formatted for easy readability in Telegram. If the RSS article contains an OpenGraph `<meta>` image tag, the image URL is included when publishing the post.
4. Articles (along with their metadata) are stored in an SQLite database to track publishing history and avoid duplicates.
5. Articles older than 7 days are automatically removed from the database to save storage and ensure relevance. To change this duration, modify the `cleanup_old_articles` function in the code.
   * Note: The bot processes only the latest 30 articles for efficiency. To increase the storage duration to 30 days or any other value, modify the `cleanup_old_articles` function in the code accordingly.
5. The bot publishes content directly to the specified Telegram channel, optionally including an image extracted from the article.

---

## Excluded Files

The following files are excluded from the Git repository:

- `.env`: Contains sensitive API keys and paths unique to your local setup.
- `articles.db`: The SQLite database file used for storing tracked article records. It is created automatically during the bot's first run.

---

## Dependencies

The bot requires the following dependencies, as specified in the `requirements.txt` file:

- **feedparser**: To retrieve and parse RSS feeds.
- **beautifulsoup4**: Cleans up raw HTML from articles.
- **python-telegram-bot**: Facilitates communication with the Telegram API.
- **openai**: Powers GPT-based filtering and content generation.
- **python-dotenv**: Manages environment-based configurations.
- **sqlite3**: Handles article storage for duplicate prevention.
- **lxml**: Provides robust HTML and XML parsing capabilities.
- **APScheduler**: Enables periodic task scheduling to continuously fetch and manage RSS updates.

You can find all dependencies in the `requirements.txt` file. Install them using:

```bash
pip install -r requirements.txt
```

### Key Dependencies

- **feedparser**: To retrieve and parse RSS feeds.
- **beautifulsoup4**: Cleans up raw HTML from articles.
- **python-telegram-bot**: Facilitates Telegram API communication.
- **openai**: Powers GPT-based filtering and content generation.
- **python-dotenv**: Manages environment-based configurations.
- **sqlite3**: Handles article storage for duplicate prevention.

## Supported Use Cases

- Posting curated news to tech channels.
- Sharing relevant, non-promotional content in niche Telegram groups.
- Generating marketing or branded content using custom OpenAI prompts to tailor wording and tone.
- Automating publication of academic or research articles for specific audiences.

## Supported Use Cases

- Posting curated news to tech channels.
- Sharing relevant, non-promotional content in niche Telegram groups.
- Building audience engagement while reducing manual effort.

---

## License

This project is licensed under [insert license type, e.g., MIT License]. Refer to the `LICENSE` file for more details.

---

## Contribution

We welcome contributions to improve the bot! If you wish to contribute:

1. Fork this repository.
2. Create a feature branch (`git checkout -b feature-name`).
3. Commit your changes and push them (`git push origin feature-name`).
4. Submit a pull request (PR).

---

## Issues

If you encounter any issues, please open a GitHub issue with detailed information about the problem.

Start automating your Telegram channel with **RSS2Telegram Bot** today! Configure and customize it to fit your goals effortlessly.
