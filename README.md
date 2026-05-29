# AUTH Gym Booking Automation

Automatically books the **Fitness Center** at the [Aristotle University of Thessaloniki gym portal](https://gym.auth.gr/reservations/) for every workday of the next week. Optionally sends a Telegram notification on each successful booking.

## How it works

1. Logs in using your institutional (ΑΠΘ) credentials
2. Navigates to the Court Reservations section
3. For each weekday (Mon–Fri) of the upcoming week, selects the Fitness Center, picks the first available slot from a prioritised list, and confirms the booking
4. Sends a Telegram message with the booking details

## Prerequisites

- Python 3.10+
- Google Chrome (or Brave — see comments in the script)
- [ChromeDriver](https://chromedriver.chromium.org/) matching your Chrome version, on your `PATH`

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root:

```env
AUTH_USERNAME=your_auth_username
AUTH_PASSWORD=your_auth_password

# Optional — remove if you don't want Telegram notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

> **Never commit `.env` to version control.** It is already listed in `.gitignore`.

## Usage

```bash
python gym_booking.py
```

The browser window will remain open after execution so you can verify the bookings manually.

To run headlessly (no visible browser), uncomment the `--headless=new` line inside `build_driver()`.

## Preferred time slots

The script tries the following slots in order, picking the first available one per day:

```
12:00 → 14:30 → 15:30 → 16:30 → 17:30 → 18:30
```

Edit the `PREFERRED_TIMES` list in `gym_booking.py` to change the order or add new slots.
