import pandas as pd
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager

def parse_grams(serving_size_text):
    """Extracts gram quantity from a string like '4oz (129g)'."""
    if not serving_size_text:
        return 'N/A'
    match = re.search(r'\((\d+)\s*g\)', serving_size_text)
    return int(match.group(1)) if match else 'N/A'

def scrape_ncsu_dining():
    """
    Scrapes the NC State dining website for weekly menu nutrition information.
    """
    # --- 1. Setup Selenium WebDriver ---
    print("Setting up browser...")
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
   # options.add_argument('--headless')  # Run browser in the background
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("start-maximized")
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 10)

    base_url = "https://netmenu2.cbord.com/NetNutrition/ncstate-dining"
    print(f"Navigating to {base_url}")
    driver.get(base_url)
    # --- ADD THIS BLOCK TO HANDLE THE WELCOME POPUP ---
    try:
    # Wait for the "Continue" button to be clickable and then click it
        continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="cbo_nn_mobileDisclaimer"]/div/section/div[3]/div[2]/button')))
        continue_button.click()
        print("👍 Clicked the disclaimer popup.")
        wait.until(EC.invisibility_of_element_located((By.ID, "cbo_nn_mobileDisclaimer")))
        print("✅ Popup has disappeared. Now searching for dining halls.")
    except TimeoutException:
    # If the popup doesn't appear, just print a message and continue
        print("ℹ️ Disclaimer popup not found, continuing...")
        pass
# ----------------------------------------------------
    all_food_data = []
    
    # --- 2. Get All Dining Hall Locations ---
    try:
        wait.until(EC.presence_of_element_located((By.ID, "unitsPanel")))
        location_elements = driver.find_elements(By.CSS_SELECTOR, "#unitsPanel a")
        location_info = []
        for loc in location_elements:
            onclick_text = loc.get_attribute('onclick')
            # First, check if the onclick attribute even exists
            if onclick_text:
                match = re.search(r"unitsSelectUnit\((\d+)\)", onclick_text)
            # Second, check if our regular expression found a match
            if match:
                location_id = match.group(1)
                location_name = loc.text
                location_info.append({'name': location_name, 'id': location_id})        
        print(f"Found {len(location_info)} dining locations.")
    except TimeoutException:
        print("Could not find dining hall locations. Exiting.")
        driver.quit()
        return

    # --- 3. Loop Through Each Location, Day, and Meal ---
    for location in location_info:
        print(f"\n--- Scraping Location: {location['name']} ---")
        driver.get(base_url)
        try:
            continue_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="cbo_nn_mobileDisclaimer"]/div/section/div[3]/div[2]/button')))
            continue_button.click()
            wait.until(EC.invisibility_of_element_located((By.ID, "cbo_nn_mobileDisclaimer")))
        except TimeoutException:
            pass
        try:
            # Click on the location link
            
            
            loc_link = wait.until(EC.element_to_be_clickable((By.XPATH, f"//a[contains(@onclick, \"unitsSelectUnit({location['id']})\")]")))
            loc_link.click()

            day_containers = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section.card")))
          # 2. Loop through each day's container
            for i in range(len(day_containers)):
                day_containers = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section.card")))
                day_container = day_containers[i]
                date_str = day_container.find_element(By.TAG_NAME, "header").text.strip()

                # 4. Get all the meal links (Breakfast, Lunch, Dinner) inside this container
                # Corresponds to: <div class="cbo_nn_mealNameLinks"> -> <a>
                meal_links = day_container.find_elements(By.CSS_SELECTOR, ".cbo_nn_menuLinkCell a")
                
                # 5. Loop through each meal for that specific day
                for j in range(len(meal_links)):
                    day_containers_refresh = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section.card")))
                    day_container_refresh = day_containers_refresh[i]
                    meal_links_refresh = day_container_refresh.find_elements(By.CSS_SELECTOR, ".cbo_nn_menuLinkCell a")
                    meal_link = meal_links_refresh[j]


                    meal_name = meal_link.text
                    meal_link.click()
                    print(f"  -> Scraping: {date_str} - {meal_name}")
                        # --- 4. Loop Through Each Food Item ---
                    try:
                        print("      -> Expanding all food categories...")
                        category_dropdowns = wait.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "cbo_nn_itemGroupRow")))
                        for dropdown in category_dropdowns:
                            try:
                                # Scroll the element into view and click it to expand
                                driver.execute_script("arguments[0].scrollIntoView(true);", dropdown)
                                dropdown.click()
                                # A small pause to allow items to load/animate
                                time.sleep(0.5) 
                            except Exception as e:
                                print(f"        Warning: Could not click a category dropdown. {e}")
                        print("      -> Scraping all visible food items...")
                        food_item_links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[id^='showNutrition_']")))
                        num_foods = len(food_item_links)

                        for i in range(num_foods):
                                    # Re-find elements in each iteration to prevent StaleElementReferenceException
                                    current_food_links = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[id^='showNutrition_']")))
                                    food_link = current_food_links[i]
                                    food_name = food_link.text
                                    main_window_handle = driver.current_window_handle
                                    
                                    # Click food item to open nutrition popup
                                    food_link.click()
                                    
                                    try:
                                        print("        > Waiting for nutrition modal...")
                                        #modal = wait.until(EC.presence_of_element_located_((By.ID, "cbo_nn_nutritionDialog")))
                                        time.sleep(0.5)
                                        # --- 5. Scrape Data from the Nutrition Popup ---
                                        # Define all possible fields with 'N/A' as default
                                        food_details = {
                                        'Date': date_str,
                                        'Location': location['name'],
                                        'Meal': meal_name,
                                        'Food Name': food_name,
                                        'Serving Size': 'N/A',
                                        'Serving Size (g)': 'N/A',
                                        'Calories': 'N/A',
                                        'Calories from Fat': 'N/A',
                                        'Total Fat': 'N/A',
                                        'Saturated Fat': 'N/A',
                                        'Trans Fat': 'N/A',
                                        'Sodium': 'N/A',
                                        'Total Carbohydrate': 'N/A',
                                        'Dietary Fiber': 'N/A',
                                        'Sugars': 'N/A',
                                        'Protein': 'N/A',
                                        'Vitamin A': 'N/A',
                                        'Vitamin C': 'N/A',
                                        'Calcium': 'N/A',
                                        'Iron': 'N/A'
                                    }

                                        serving_size = driver.find_element(By.XPATH, '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[3]/td').text

                                        food_details['Serving Size'] = serving_size
                                        food_details['Serving Size (g)'] = parse_grams(serving_size)


                                        calories = driver.find_element(By.XPATH, '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[5]/td/table/tbody/tr/td[1]/span[2]').text
                                        food_details['Calories'] = calories

                                        total_fat = driver.find_element(By.XPATH, '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[7]/td/table/tbody/tr/td/table/tbody/tr/td[2]/span').text
                                        food_details['Total Fat'] = total_fat
                                        
                                        saturated_fat = driver.find_element(By.XPATH, '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[8]/td/table/tbody/tr/td/table/tbody/tr/td[2]/span').text
                                        food_details['Saturated Fat'] = saturated_fat

                                        sodium = driver.find_element(By.XPATH, '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[10]/td/table/tbody/tr/td/table/tbody/tr/td[2]/span').text
                                        food_details['Sodium'] = sodium

                                        carbs = driver.find_element(By.XPATH, '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[11]/td/table/tbody/tr/td/table/tbody/tr/td[2]/span').text
                                        food_details['Total Carbohydrate'] = carbs

                                        protein = driver.find_element(By.XPATH, '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[12]/td/table/tbody/tr/td/table/tbody/tr/td[2]/span').text
                                        food_details['Protein'] = protein
                                        
                            
                                    finally:
                                        # Close popup and switch back to main window
                                        if len(driver.window_handles) > 1:
                                            driver.close()
                                        driver.switch_to.window(main_window_handle)
                            
                    except TimeoutException:
                        print(f"    No food items found for {meal['name']}.")
                    
                    print("    <- Navigating back to weekly menu")
                    driver.back()

        except Exception as e:
            print(f"An error occurred while scraping {location['name']}: {e}")
            continue

    # --- 6. Save Data to CSV ---
    driver.quit()
    if not all_food_data:
        print("\nNo data was scraped. The website structure may have changed.")
        return
        
    print("\nScraping complete. Saving data to CSV...")
    df = pd.DataFrame(all_food_data)
    # Reorder columns for clarity
    column_order = [
        'Date', 'Location', 'Meal', 'Food Name', 'Serving Size (g)', 'Calories', 
        'Total Fat', 'Saturated Fat', 'Trans Fat', 'Cholesterol', 'Sodium', 
        'Total Carbohydrate', 'Dietary Fiber', 'Sugars', 'Protein', 'Serving Size', 
        'Ingredients', 'Calories from Fat', 'Vitamin A', 'Vitamin C', 'Calcium', 'Iron'
    ]
    # Ensure all columns exist, adding any missing ones with N/A
    for col in column_order:
        if col not in df.columns:
            df[col] = 'N/A'

    df = df[column_order]
    df.to_csv('nc_state_dining_menu.csv', index=False, encoding='utf-8')
    print("✅ Success! Data saved to nc_state_dining_menu.csv")

if __name__ == '__main__':

    scrape_ncsu_dining()
