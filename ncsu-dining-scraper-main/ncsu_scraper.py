import pandas as pd
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

def clean_text(text):
    """Removes non-ascii characters and extra whitespace."""
    if not text:
        return "N/A"
    return re.sub(r'\s+', ' ', text).strip()

def extract_dynamic_nutrition(driver):
    data = {}
    
    # 1. Scrape Macros & Calories from the Table
    try:
        rows = driver.find_elements(By.CSS_SELECTOR, "#nutritionLabel table tbody tr")
        for row in rows:
            text = row.text.strip()
            
            # Calories (Start of line)
            if text.startswith("Calories"):
                match = re.search(r'Calories\s+(\d+)', text)
                if match: data['Calories'] = match.group(1)

            # Grams (Fat, Protein, Carbs)
            g_match = re.search(r'(\d+(?:\.\d+)?)\s*g', text)
            if g_match:
                value = g_match.group(1)
                if "Total Fat" in text: data['Total Fat'] = value + "g"
                elif "Carbohydrate" in text: data['Total Carbohydrate'] = value + "g"
                elif "Protein" in text: data['Protein'] = value + "g"
                elif "Sugars" in text: data['Sugars'] = value + "g"
                elif "Fiber" in text: data['Dietary Fiber'] = value + "g"
                elif "Saturated Fat" in text: data['Saturated Fat'] = value + "g"

            # Milligrams (Sodium, Cholesterol)
            mg_match = re.search(r'(\d+(?:\.\d+)?)\s*mg', text)
            if mg_match:
                value = mg_match.group(1)
                if "Sodium" in text: data['Sodium'] = value + "mg"
                elif "Cholesterol" in text: data['Cholesterol'] = value + "mg"
    except:
        pass

    # 2. Scrape Serving Size (FIXED XPATH)
    try:
        # FIX: We add "//*[@id='nutritionLabel']" to the front.
        # This forces Python to look ONLY inside the currently open popup box.
        serving_el = driver.find_element(By.XPATH, "//*[@id='nutritionLabel']//*[contains(text(), 'Serving Size')]/..")
        
        raw_serving = serving_el.text.replace("Serving Size:", "").strip()
        data["Serving Size"] = raw_serving
        
        # Debugging: Print what we found to the terminal so you can verify
        print(f"      [DEBUG] Found Serving Text: '{raw_serving}'")

        # Regex Strategy
        gram_match = re.search(r'\(\s*(\d+)\s*g\s*\)', raw_serving)
        gram_match_B = re.search(r'(\d+)\s*g', raw_serving) # Fallback for "115g" without parens
        
        if gram_match:
            data["Serving Size (g)"] = gram_match.group(1)
        elif gram_match_B:
            data["Serving Size (g)"] = gram_match_B.group(1)
        else:
            data["Serving Size (g)"] = "1"
            
    except Exception as e:
        # If we can't find it, print why
        print(f"      [DEBUG] Serving Size Error: {e}")
        data["Serving Size"] = "N/A"
        data["Serving Size (g)"] = "1"

    return data

def safe_click(driver, element):
    """Robust click with JS fallback."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.1)
        element.click()
    except Exception:
        driver.execute_script("arguments[0].click();", element)

def scrape_ncsu_dining():
    print("Setting up Google Chrome...")
    
    # --- CHROME SETUP ---
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    options.add_argument("start-maximized")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 5)

    base_url = "https://netmenu2.cbord.com/NetNutrition/ncstate-dining"
    print(f"Navigating to {base_url}")
    driver.get(base_url)

    # --- DISCLAIMER POPUP ---
    try:
        
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="cbo_nn_mobileDisclaimer"]/div/section/div[3]/div[2]/button')))
        safe_click(driver, btn)
        time.sleep(1)
        print(" Accepted Disclaimer")
    except TimeoutException:
        print(" No disclaimer found.")

    all_food_data = []

    # --- GET LOCATIONS ---
    try:
        wait.until(EC.presence_of_element_located((By.ID, "unitsPanel")))
        # We grab text first to avoid Stale Elements later
        loc_elements = driver.find_elements(By.CSS_SELECTOR, "#unitsPanel .unit a")
        locations = [l.text for l in loc_elements if l.text]
        print(f"Found Locations: {locations}")
    except Exception:
        print("Could not find locations. Exiting.")
        driver.quit()
        return

    # --- MAIN LOOP ---
    for loc_name in locations:
        # Filter: Only scrape Dining Halls (Fountain/Clark/Oval) to save time?
        # Remove this if check if you want ALL cafes.
        if "Fountain" not in loc_name and "Clark" not in loc_name and "Oval" not in loc_name:
             continue 

        print(f"\n--- Entering {loc_name} ---")
        
        # Click Location
        try:
            loc_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, loc_name)))
            safe_click(driver, loc_link)
        except Exception:
            print(f"Skipping {loc_name} (Click failed)")
            continue

        # Get Days (Limit to first 2 days for testing speed)
        try:
            days = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section.card")))
        except:
            # If no menu, go back
            driver.execute_script("window.history.go(-1)")
            continue

        # Loop through days by INDEX to prevent Stale Elements
        for i in range(min(len(days), 2)):
            # Refresh DOM reference
            days = driver.find_elements(By.CSS_SELECTOR, "section.card")
            if i >= len(days): break
            
            day_header = days[i].find_element(By.TAG_NAME, "header").text
            print(f"  Processing: {day_header}")

            # Get Meals
            meals = days[i].find_elements(By.CSS_SELECTOR, ".cbo_nn_menuLinkCell a")
            meal_names = [m.text for m in meals]

            for meal_name in meal_names:
                print(f"    -> Meal: {meal_name}")
                
                # Click Meal (Robust Finding)
                try:
                    current_day = driver.find_elements(By.CSS_SELECTOR, "section.card")[i]
                    meal_link = current_day.find_element(By.PARTIAL_LINK_TEXT, meal_name)
                    safe_click(driver, meal_link)
                except Exception:
                    print("      Could not click meal.")
                    continue

                # Expand Categories (JS Optimization)
                try:
                    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cbo_nn_itemGroupRow")))
                    driver.execute_script("document.querySelectorAll('.cbo_nn_itemGroupRow').forEach(b => b.click())")
                    time.sleep(1) # Wait for animation
                except:
                    pass

                # Get Food Items
                food_links = driver.find_elements(By.CSS_SELECTOR, "a[id^='showNutrition']")
                print(f"      Found {len(food_links)} items.")

                # Loop Foods by INDEX
                # Loop Foods by INDEX
                # Loop Foods by INDEX
                for f_idx in range(len(food_links)):
                    try:
                        # Re-find list to avoid Stale Elements
                        current_foods = driver.find_elements(By.CSS_SELECTOR, "a[id^='showNutrition']")
                        if f_idx >= len(current_foods): break
                        
                        food_el = current_foods[f_idx]
                        f_name = clean_text(food_el.text)
                        
                        # Open Modal
                        safe_click(driver, food_el)
                        wait.until(EC.visibility_of_element_located((By.ID, "nutritionLabel")))
                        
                        # --- DYNAMIC EXTRACTION ---
                        nutrients = extract_dynamic_nutrition(driver)
                        nutrients['Food Name'] = f_name
                        nutrients['Meal'] = meal_name
                        nutrients['Location'] = loc_name
                        nutrients['Date'] = day_header
                        
                        all_food_data.append(nutrients)

                        if len(all_food_data) % 10 == 0:
                            temp_df = pd.DataFrame(all_food_data)
                            # Ensure columns exist before saving
                            cols = ['Date', 'Location', 'Meal', 'Food Name', 'Serving Size (g)', 'Calories', 'Protein', 'Total Carbohydrate', 'Total Fat', 'Sugars']
                            for c in cols:
                                if c not in temp_df.columns: temp_df[c] = 'N/A'
                            
                            temp_df = temp_df[cols] # Reorder
                            temp_df.to_csv("nc_state_dining_menu.csv", index=False)
                            print(f"    💾 Saved progress ({len(all_food_data)} items)")
                       
                        if len(all_food_data) % 5 == 0:
                            print(f"\n--- 📊 Live Data Feed ({len(all_food_data)} items collected) ---")
                            recent_items = all_food_data[-5:]
                            
                            # Print Header
                            print(f"{'Food Name':<25} | {'Cal':<5} | {'Prot':<5} | {'Carb':<5} | {'Fat':<5}")
                            print("-" * 65)
                            
                            for item in recent_items:
                                name = item.get('Food Name', 'Unknown')[:23]
                                cal = item.get('Calories', '-')
                                prot = item.get('Protein', '-')
                                carb = item.get('Total Carbohydrate', '-')
                                fat = item.get('Total Fat', '-')
                                
                                print(f"{name:<25} | {cal:<5} | {prot:<5} | {carb:<5} | {fat:<5}")
                            print("-" * 65)
                        
                        # Close Modal (Must be indented inside the TRY block)
                        close_btn = driver.find_element(By.ID, "btn_nn_nutrition_close")
                        safe_click(driver, close_btn)
                        wait.until(EC.invisibility_of_element_located((By.ID, "nutritionLabel")))
                        
                    except Exception as e:
                        # Force close modal if something broke
                        try:
                            driver.find_element(By.ID, "btn_nn_nutrition_close").click()
                        except:
                            pass

                # Go Back to Day View
                try:
                    back_btn = driver.find_element(By.CSS_SELECTOR, "#itemPanel nav a")
                    safe_click(driver, back_btn)
                    time.sleep(1) 
                except:
                    driver.back()

        # Go Back to Locations (Home)
        driver.get(base_url) 
        try:
             # Handle disclaimer if it reappears
            wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Continue')]"))).click()
        except:
            pass

    driver.quit()
    
    # Save Data
    if all_food_data:
        df = pd.DataFrame(all_food_data)
        # Ensure standard columns exist
        cols = ['Date', 'Location', 'Meal', 'Food Name', 'Serving Size', 'Calories', 'Protein', 'Total Carbohydrate', 'Total Fat', 'Sugars']
        for c in cols:
            if c not in df.columns: df[c] = 'N/A'
            
        df.to_csv("nc_state_dining_menu.csv", index=False)
        print("\n✅ Success! Data saved to nc_state_dining_menu.csv")
    else:
        print("\n❌ No data scraped.")

if __name__ == '__main__':
    scrape_ncsu_dining()
