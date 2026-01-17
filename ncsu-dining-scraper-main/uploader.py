import pandas as pd
import os
import json
import time
import random
from getpass import getpass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURATION ---
UPLOAD_FILE = 'to_upload.csv'
HISTORY_FILE = 'upload_history.json'

def setup_driver():
    """Sets up the Chrome WebDriver."""
    print("🔌 Setting up Google Chrome Driver...")

    chrome_options = Options()
    chrome_options.add_argument("start-maximized")
    # chrome_options.add_argument("--headless") # NEVER run headless for MFP (Captchas!)
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    # Use the automatic manager (Same as your scraper)
    service = Service(ChromeDriverManager().install())
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def update_history(item_id):
    """Adds a successful upload to the history file."""
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
    
    history.append(item_id)
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)




def main():
    # 1. Check for data
    if not os.path.exists(UPLOAD_FILE):
        print(" No 'to_upload.csv' found. Run deduplicate_data.py first.")
        return

    queue = pd.read_csv(UPLOAD_FILE)
    if queue.empty:
        print(" Queue is empty! Nothing to upload.")
        return

    print(f" Preparing to upload {len(queue)} items to MyFitnessPal.")

    driver = setup_driver()
    wait = WebDriverWait(driver, 15)

    try:
        print(" Logging in...")
        driver.get("https://www.myfitnesspal.com/account/login")
            
            # Accept Cookies if popped up
       
        input(" Press ENTER in this terminal once you are fully logged in and see your Dashboard...")
        print(" Login confirmed! Ready to add upload logic.")
    except Exception as e:
        print(f"\n Critical Error: {e}")
        
if __name__ == "__main__":
    main()