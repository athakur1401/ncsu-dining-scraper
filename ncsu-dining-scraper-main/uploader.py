import pandas as pd
import os
import json
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from urllib3.exceptions import MaxRetryError

# --- CONFIGURATION ---
UPLOAD_FILE = 'to_upload.csv'
HISTORY_FILE = 'upload_history.json'
DEBUG_PORT = 9222 

def setup_existing_driver():
    print(f"🔌 Connecting to existing Chrome on port {DEBUG_PORT}...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    service = Service(ChromeDriverManager().install())
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("✅ Connected successfully!")
        return driver
    except Exception as e:
        print("\n❌ CRITICAL ERROR: Could not connect to Chrome.")
        print(f"Details: {e}")
        return None

def update_history(item_id):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
    history.append(item_id)
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def safe_type_xpath(driver, xpath, text, submit_after=False):
    """ Targets a specific XPath, clears it (Ctrl+A -> Del), and types. """
    try:
        target_elem = driver.find_element(By.XPATH, xpath)
        
        # Scroll & Focus
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", target_elem)
        time.sleep(0.1)
        try: target_elem.click()
        except: pass
        
        # Nuclear Clear
        target_elem.send_keys(Keys.CONTROL + "a")
        time.sleep(0.05)
        target_elem.send_keys(Keys.BACKSPACE)

        # Type
        if text is not None and str(text) != 'nan':
            for char in str(text):
                target_elem.send_keys(char)
                time.sleep(random.uniform(0.01, 0.03))
        
        if submit_after:
            time.sleep(0.5)
            target_elem.send_keys(Keys.ENTER)
        
        return True

    except Exception as e:
        print(f"   ⚠️ Could not find box at XPath: {xpath}")
        return False

def force_click_create_food(driver):
    """ Targets the 'Create Food' button on the duplicate page. """
    print("   [Duplicate Check] Scanning...", end="")
    time.sleep(2)

    if "duplicate" not in driver.current_url and "similar" not in driver.page_source:
        print(" No warning.")
        return

    print(" DETECTED! Clicking 'Create Food'...")
    selectors = [
        "//button[contains(text(), 'Create Food')]",
        "//button[text()='Create Food']",
        "input[value='Create Food']",
        "button.MuiButton-containedPrimary"
    ]

    for selector in selectors:
        try:
            if "//" in selector: btn = driver.find_element(By.XPATH, selector)
            else: btn = driver.find_element(By.CSS_SELECTOR, selector)
            driver.execute_script("arguments[0].click();", btn)
            print("   ✅ Clicked!")
            
            # WAIT FOR PAGE LOAD
            print("   ⏳ Waiting 5s for Step 2 to load...")
            time.sleep(5) 
            return
        except: continue
    
    print("   ⚠️ Button missed. Sending ENTER.")
    webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()
    time.sleep(5)

def main():
    if not os.path.exists(UPLOAD_FILE):
        print("❌ No 'to_upload.csv' found.")
        return

    queue = pd.read_csv(UPLOAD_FILE)
    if queue.empty:
        print("🎉 Queue is empty! Nothing to upload.")
        return

    print(f"🚀 Preparing to upload {len(queue)} items.")

    driver = setup_existing_driver()
    if not driver: return

    wait = WebDriverWait(driver, 15)

    try:
        try:
            if "food/submit" not in driver.current_url:
                print("🔄 Navigating to Submit page...")
                driver.get("https://www.myfitnesspal.com/food/submit")
        except:
            print("❌ Connection lost. Please restart Chrome.")
            return
        
        queue_list = list(queue.iterrows())
        total_items = len(queue_list)

        print("✅ Ready. Starting upload loop...")

        for i, (index, row) in enumerate(queue_list):
            is_last_item = (i == total_items - 1)
            
            food_name = row['Food Name']
            calories = row['Calories']
            if pd.isna(calories) or str(calories).strip() in ['N/A', '-', '']: continue
                
            unique_id = f"{food_name}_{calories}"
            display_name = f"[NCSU] {food_name}"
            
            protein = str(row['Protein']).replace('g', '').strip()
            carbs = str(row['Total Carbohydrate']).replace('g', '').strip()
            fat = str(row['Total Fat']).replace('g', '').strip()
            location = str(row.get('Location', '')).replace(' Dining Hall', '')
            brand_name = f"NC State Dining - {location}"

            print(f"   Uploading ({i+1}/{total_items}): {display_name}...", end="")

            try:
                # Ensure we are on start page
                if "food/submit" not in driver.current_url:
                    driver.get("https://www.myfitnesspal.com/food/submit")

                # Step 1: Wait for Description
                try:
                    wait.until(EC.visibility_of_element_located((By.ID, "description")))
                except:
                    print(" (Refreshing...) ", end="")
                    driver.refresh()
                    wait.until(EC.visibility_of_element_located((By.ID, "description")))

                # Fill Step 1
                try:
                    desc_box = driver.find_element(By.ID, "description")
                    desc_box.send_keys(Keys.CONTROL + "a"); desc_box.send_keys(Keys.BACKSPACE)
                    desc_box.send_keys(display_name)
                except: pass

                try:
                    brand_box = driver.find_element(By.ID, "brand")
                    if not brand_box: brand_box = driver.find_element(By.NAME, "brand")
                    brand_box.send_keys(Keys.CONTROL + "a"); brand_box.send_keys(Keys.BACKSPACE)
                    brand_box.send_keys(brand_name)
                    time.sleep(0.5)
                    brand_box.send_keys(Keys.ENTER) 
                except: pass
                
                # Duplicate Check
                force_click_create_food(driver)

                # --- STEP 2: NUTRITION FACTS ---
                
                # 1. Soft Gatekeeper
                try:
                    wait.until(EC.presence_of_element_located((By.TAG_NAME, "input")))
                    time.sleep(1) 
                except:
                    print(" ⚠️ Page didn't load. Skipping.")
                    continue

                serving_desc = "serving"
                if str(row['Serving Size (g)']) not in ['N/A', '1']:
                     serving_desc += f" ({row['Serving Size (g)']}g)"

                # --- CORRECTED XPATHS (No typos!) ---
                
                # Serving Value
                safe_type_xpath(driver, "/html/body/div/div/div/div/div/main/div/div/div/form/div[4]/div[1]/div[1]/div/div/div[1]/div/input", 1)
                
                # Serving Unit
                safe_type_xpath(driver, "/html/body/div/div/div/div/div/main/div/div/div/form/div[4]/div[1]/div[1]/div/div/div[2]/div/input", serving_desc)
                
                # Calories
                safe_type_xpath(driver, "/html/body/div/div/div/div/div/main/div/div/div/form/div[4]/div[2]/div/div[1]/div[1]/div/div/div/input", calories)
                
                # Total Fat
                safe_type_xpath(driver, "/html/body/div/div/div/div/div/main/div/div/div/form/div[4]/div[2]/div/div[1]/div[2]/div/div/div/input", fat)
                
                # Total Carbs
                safe_type_xpath(driver, "/html/body/div/div/div/div/div/main/div/div/div/form/div[4]/div[2]/div/div[2]/div[3]/div/div/div/input", carbs)
                
                # Protein
                safe_type_xpath(driver, "/html/body/div/div/div/div/div/main/div/div/div/form/div[4]/div[2]/div/div[2]/div[6]/div/div/div/input", protein)


                # --- SAVE LOGIC ---
                if is_last_item:
                    print(" [TEST: Would Click Save]")
                    # UNCOMMENT NEXT LINE FOR REAL RUN
                    # driver.find_element(By.CSS_SELECTOR, "input[value='Save Changes']").click() 
                else:
                    print(" [TEST: Would Loop]")
                    # UNCOMMENT NEXT LINE FOR REAL RUN
                    # driver.find_element(By.CSS_SELECTOR, "input[value='Save and Create Another']").click() 
                    
                    # Manual reset for test mode
                    driver.get("https://www.myfitnesspal.com/food/submit")
                    time.sleep(1.5) 

                update_history(unique_id)
                print(" ✅ Done.")

            except Exception as e:
                print(f" ❌ Failed: {e}")
                try:
                    driver.get("https://www.myfitnesspal.com/food/submit")
                except:
                    print("❌ Browser connection lost.")
                    break

    except Exception as e:
        print(f"\n💥 Critical Script Error: {e}")

    print("\n🏁 Session Complete.")

if __name__ == "__main__":
    main()
