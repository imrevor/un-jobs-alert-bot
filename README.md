# UN Jobs Alert Bot

Free Telegram bot for UN and international development job alerts.

## Deploy to Railway

1. Push this repo to GitHub
2. Connect Railway to your GitHub repo
3. Add environment variable: `TELEGRAM_BOT_TOKEN`
4. Deploy — done!

## Files

- `bot.py` — main bot (commands, filters, IMREVOR hooks, auto-notifications)
- `scraper.py` — scrapes unjobs.org + impactpool.org
- `database.py` — SQLite database (users, filters, jobs, counters)
- `requirements.txt` — Python dependencies
- `Procfile` — Railway/Heroku process definition
- `runtime.txt` — Python version
- `landing/index.html` — SEO landing page (host on GitHub Pages)

## Bot Link

https://t.me/UNJobsAlertBot
