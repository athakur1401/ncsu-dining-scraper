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

UPLOAD_FILE = 'to_upload.csv'
HISTORY_FILE = 'upload_history.json'
DEBUG_PORT = 9222 

def setup_existing_driver():
    print(f" Connecting to Chrome on port {DEBUG_PORT}...")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    service = Service(ChromeDriverManager().install())
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print(" Connected!")
        return driver
    except:
        print(" CRITICAL: Make sure Chrome is open with port 9222.")
        return None

def update_history(item_id):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f: history = json.load(f)
    history.append(item_id)
    with open(HISTORY_FILE, 'w') as f: json.dump(history, f)

def safe_type_id(driver, element_id, text, submit_after=False):
   
    try:
        target_elem = driver.find_element(By.ID, element_id)
        
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", target_elem)
        time.sleep(0.1)
        try: target_elem.click()
        except: pass
        
        target_elem.send_keys(Keys.CONTROL + "a")
        time.sleep(0.05)
        target_elem.send_keys(Keys.BACKSPACE)

        if text is not None and str(text) != 'nan':
            for char in str(text):
                target_elem.send_keys(char)
                time.sleep(random.uniform(0.01, 0.03))
        
        if submit_after:
            time.sleep(0.5)
            target_elem.send_keys(Keys.ENTER)
        return True
    except:
        print(f"Could not find box with ID: '{element_id}'")
        return False

def force_click_create_food(driver):
    time.sleep(2)
    if "duplicate" not in driver.current_url and "similar" not in driver.page_source:
        print(" No warning.")
        return

    selectors = ["//button[contains(text(), 'Create Food')]", "input[value='Create Food']"]
    
    for selector in selectors:
        try:
            btn = driver.find_element(By.XPATH, selector)
            driver.execute_script("arguments[0].click();", btn)
            print("    Clicked! Waiting for Step 2...")
            time.sleep(4)
            return
        except: continue
    
    # Fallback
    webdriver.ActionChains(driver).send_keys(Keys.ENTER).perform()
    time.sleep(4)

def main():
    if not os.path.exists(UPLOAD_FILE): return

    queue = pd.read_csv(UPLOAD_FILE)
    driver = setup_existing_driver()
    if not driver: return
    wait = WebDriverWait(driver, 10)

    for i, (index, row) in enumerate(queue.iterrows()):
        food_name = row['Food Name']
        calories = row['Calories']
        if pd.isna(calories) or str(calories).strip() in ['N/A', '-', '']: continue
            
        unique_id = f"{food_name}_{calories}"
        display_name = f"[NCSU] {food_name}"
        location = str(row.get('Location', '')).replace(' Dining Hall', '')
        brand_name = f"NC State Dining - {location}"

        print(f"   Uploading ({i+1}/{len(queue)}): {display_name}...", end="")

        try:
            if "food/submit" not in driver.current_url:
                driver.get("https://www.myfitnesspal.com/food/submit")

            # STEP 1: Using IDs from X-Ray
            try: wait.until(EC.visibility_of_element_located((By.ID, "description")))
            except: driver.refresh(); time.sleep(2)
            
            safe_type_id(driver, "description", display_name) # Box #2
            safe_type_id(driver, "brand", brand_name, submit_after=True) # Box #1
            
            # Duplicate Check
            force_click_create_food(driver)

            # STEP 2: Using IDs from X-Ray
            # Wait for 'caloriesCapitalized' to confirm page load (The secret ID we found!)
            try:
                wait.until(EC.visibility_of_element_located((By.ID, "caloriesCapitalized")))
            except:
                print("  Page didn't load. Skipping.")
                continue

            serving_desc = "serving"
            if str(row['Serving Size (g)']) not in ['N/A', '1']:
                    serving_desc += f" ({row['Serving Size (g)']}g)"

            # --- THE GOLDEN IDs ---
            serving_value = str(row['Serving Size (g)'])
            if serving_value in ['N/A', 'nan', '']: serving_value = "1"    
            safe_type_id(driver, "serving", serving_value) 
            safe_type_id(driver, "unit", "g") # Box #4
            safe_type_id(driver, "caloriesCapitalized", calories) # Box #6 (The tricky one!)
            safe_type_id(driver, "total_fat", row['Total Fat'] if str(row['Total Fat']) != 'nan' else 0) # Box #7
            safe_type_id(driver, "carbohydrates", row['Total Carbohydrate'] if str(row['Total Carbohydrate']) != 'nan' else 0) # Box #17
            safe_type_id(driver, "protein", row['Protein'] if str(row['Protein']) != 'nan' else 0) # Box #20

            is_last_item = (i == len(queue) - 1)
            if is_last_item:
                print("    Saving Final Item...")
                # Click "Save Changes" (Finishes the batch)
                save_btn = driver.find_element(By.CSS_SELECTOR, "input[value='Save Changes']")
                driver.execute_script("arguments[0].click();", save_btn)
                update_history(unique_id)
                print("BATCH COMPLETE")
                
            else:
                print(" Saving & Looping")
                # Click "Save and Create Another" (Prepares for next item)
                loop_btn = driver.find_element(By.CSS_SELECTOR, "input[value='Save and Create Another']")
                driver.execute_script("arguments[0].click();", loop_btn)
                
                # Wait for the form to clear/reload for the next item
                time.sleep(2) 
                update_history(unique_id)
                print(" Saved. Moving to next...")
            
            # Loop Reset
            print(" [Test Loop]")
            driver.get("https://www.myfitnesspal.com/food/submit")
            time.sleep(1)
            update_history(unique_id)

        except Exception as e:
            print(f"  Error: {e}")
            try: driver.get("https://www.myfitnesspal.com/food/submit")
            except: break

if __name__ == "__main__":
    main()
