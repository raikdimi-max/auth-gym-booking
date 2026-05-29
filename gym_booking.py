import os
import time
import logging
import datetime
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# Configuration
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

USERNAME = os.getenv("AUTH_USERNAME")
PASSWORD = os.getenv("AUTH_PASSWORD")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BASE_URL = "https://gym.auth.gr/reservations/"
PREFERRED_TIMES = ["12:00", "14:30", "15:30", "16:30", "17:30", "18:30"]


def get_next_week_workdays() -> list[datetime.date]:
    """Returns Monday–Friday of the next calendar week."""
    today = datetime.date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + datetime.timedelta(days=days_until_monday)
    return [next_monday + datetime.timedelta(days=i) for i in range(5)]


# ==========================================
# Notifications
# ==========================================

def send_telegram_message(text: str) -> None:
    """Sends a notification to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.info("Telegram credentials not set — skipping notification.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except requests.RequestException as e:
        log.error("Failed to send Telegram message: %s", e)


# ==========================================
# Browser helpers
# ==========================================

def js_click(driver, element) -> None:
    """Scrolls an element into view and clicks it via JavaScript."""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.5)
    driver.execute_script("arguments[0].click();", element)


def wait_and_click(driver, by, locator, timeout: int = 10):
    """Waits for an element to be clickable and clicks it."""
    element = WebDriverWait(driver, timeout).until(
        EC.element_to_be_clickable((by, locator))
    )
    js_click(driver, element)
    return element


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("detach", True)
    # Uncomment for Brave:
    # options.binary_location = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
    # Uncomment to run headless:
    # options.add_argument("--headless=new")
    return webdriver.Chrome(options=options)


# ==========================================
# Booking steps
# ==========================================

def login(driver) -> None:
    """Navigates to the portal and logs in with institutional credentials."""
    log.info("Navigating to gym portal…")
    driver.get(BASE_URL)

    login_link = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (By.LINK_TEXT, "Σύνδεση με ιδρυματικό λογαριασμό ΑΠΘ")
        )
    )
    driver.execute_script("arguments[0].click();", login_link)

    username_field = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "usernameUserInput"))
    )
    username_field.send_keys(USERNAME)

    password_field = driver.find_element(By.ID, "password")
    password_field.send_keys(PASSWORD)
    password_field.send_keys(Keys.RETURN)

    log.info("Login submitted — waiting for redirect…")
    time.sleep(3)


def open_court_reservations(driver) -> None:
    """Clicks the 'Court Reservations' tile if present."""
    try:
        wait_and_click(
            driver,
            By.XPATH,
            "//a[.//h2[text()='Κρατήσεις Γηπέδων']]",
        )
        log.info("Entered Court Reservations section.")
    except Exception:
        log.info("'Court Reservations' tile not found — assuming correct page.")


def select_fitness_center(driver) -> None:
    """Selects the Fitness Center facility and advances to the date step."""
    wait_and_click(
        driver,
        By.XPATH,
        "//*[contains(text(), 'Αίθουσα Fitness Center')]",
        timeout=15,
    )
    wait_and_click(
        driver,
        By.XPATH,
        "//button[contains(., 'Ημερομηνία & Ώρα')]",
    )
    log.info("Fitness Center selected.")


def select_date(driver, target_date: datetime.date) -> bool:
    """Clicks the target date on the calendar. Returns False if unavailable."""
    label = f"{target_date.strftime('%B')} {target_date.day}, {target_date.year}"
    try:
        wait_and_click(driver, By.XPATH, f"//span[@aria-label='{label}']", timeout=5)
        log.info("Date selected: %s", label)
        return True
    except Exception:
        log.warning("Date %s not clickable on calendar — skipping.", label)
        return False


def select_time_slot(driver) -> tuple[bool, str]:
    """
    Iterates through PREFERRED_TIMES and picks the first available slot.
    Returns (success, selected_time_str).
    """
    for time_str in PREFERRED_TIMES:
        log.info("  Checking slot %s…", time_str)
        try:
            time_element = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable(
                    (By.XPATH, f"//*[contains(text(), '{time_str}')]")
                )
            )
            js_click(driver, time_element)

            # Confirm the UI advanced to the details step
            WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.ID, "details-step"))
            )
            log.info("  Slot %s confirmed.", time_str)
            return True, time_str

        except Exception:
            log.info("  Slot %s unavailable — trying next…", time_str)

    return False, ""


def finalize_booking(driver) -> None:
    """Clicks through Personal Details → Overview → Book Now."""
    wait_and_click(driver, By.ID, "details-step")
    log.info("Personal Details step passed.")

    wait_and_click(driver, By.ID, "overview-step")
    log.info("Overview step passed.")

    time.sleep(2)
    wait_and_click(driver, By.ID, "booking-step")
    log.info("Booking confirmed!")


def reset_to_reservations(driver) -> None:
    """Returns to the reservations page for the next booking iteration."""
    try:
        wait_and_click(
            driver,
            By.XPATH,
            "//a[contains(@class, 'new-appointment-btn') and contains(@href, 'reservations')]",
        )
        log.info("Reset via 'New Booking' button.")
    except Exception:
        log.warning("'New Booking' button not found — forcing URL reset.")
        driver.get(BASE_URL)
    time.sleep(3)


# ==========================================
# Main orchestration
# ==========================================

def book_week(driver) -> None:
    """Books the Fitness Center for every workday of the next week."""
    open_court_reservations(driver)
    workdays = get_next_week_workdays()

    log.info("=== Starting batch booking for %d days ===", len(workdays))

    for target_date in workdays:
        label = f"{target_date.strftime('%B')} {target_date.day}, {target_date.year}"
        log.info("--- Booking: %s ---", label)

        try:
            select_fitness_center(driver)

            if not select_date(driver, target_date):
                reset_to_reservations(driver)
                continue

            success, chosen_time = select_time_slot(driver)
            if not success:
                log.error("No preferred slots available for %s — skipping.", label)
                reset_to_reservations(driver)
                continue

            finalize_booking(driver)

            send_telegram_message(
                f"✅ Gym Booking Confirmed!\n"
                f"📅 Date: {label}\n"
                f"⏰ Time: {chosen_time}\n"
                f"🏋️ Room: Fitness Center"
            )

            time.sleep(3)
            reset_to_reservations(driver)

        except Exception as e:
            log.error("Unexpected error on %s: %s — resetting session.", label, e)
            driver.get(BASE_URL)
            time.sleep(3)


def main() -> None:
    if not USERNAME or not PASSWORD:
        log.error("Missing AUTH_USERNAME or AUTH_PASSWORD in .env — aborting.")
        return

    log.info("Automation started.")
    driver = build_driver()

    try:
        login(driver)
        book_week(driver)
    finally:
        log.info("Execution complete. Browser session will remain open.")


if __name__ == "__main__":
    main()
