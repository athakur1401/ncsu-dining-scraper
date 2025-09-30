import pandas as pd
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager


def parse_grams(serving_size_text):
    """Extracts gram quantity from a string like '4oz (129g)'."""
    if not serving_size_text:
        return 'N/A'
    match = re.search(r'\((\d+)\s*g\)', serving_size_text)
    return int(match.group(1)) if match else 'N/A'


def safe_click(driver, element, desc="element"):
    """Safely click an element with scroll + JS fallback."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
        time.sleep(0.2)
        element.click()
    except Exception as e:
        print(f"      [WARN] Normal click failed on {desc}: {e}. Using JS click...")
        try:
            driver.execute_script("arguments[0].click();", element)
        except Exception as e2:
            print(f"      [ERROR] JS click also failed on {desc}: {e2}")


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

    # --- Handle the welcome popup ---
    try:
        continue_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, '//*[@id="cbo_nn_mobileDisclaimer"]/div/section/div[3]/div[2]/button')
        ))
        safe_click(driver, continue_button, "disclaimer popup")
        print("👍 Clicked the disclaimer popup.")
        wait.until(EC.invisibility_of_element_located((By.ID, "cbo_nn_mobileDisclaimer")))
        print("✅ Popup has disappeared. Now searching for dining halls.")
    except TimeoutException:
        print("ℹ️ Disclaimer popup not found, continuing...")

    all_food_data = []

    # --- 2. Get All Dining Hall Locations ---
    try:
        wait.until(EC.presence_of_element_located((By.ID, "unitsPanel")))
        location_elements = driver.find_elements(By.CSS_SELECTOR, "#unitsPanel a")
        location_info = []
        for loc in location_elements:
            onclick_text = loc.get_attribute('onclick')
            if onclick_text:
                match = re.search(r"unitsSelectUnit\((\d+)\)", onclick_text)
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

        # Handle disclaimer popup again
        try:
            continue_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="cbo_nn_mobileDisclaimer"]/div/section/div[3]/div[2]/button')
            ))
            safe_click(driver, continue_button, "disclaimer popup")
            wait.until(EC.invisibility_of_element_located((By.ID, "cbo_nn_mobileDisclaimer")))
        except TimeoutException:
            pass

        try:
            # Click on the location link
            loc_link = wait.until(EC.element_to_be_clickable(
                (By.XPATH, f"//a[contains(@onclick, \"unitsSelectUnit({location['id']})\")]")
            ))
            safe_click(driver, loc_link, f"location {location['name']}")

            day_containers = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section.card"))
            )

            # --- Loop through each day's container ---
            for day_index, day_container in enumerate(day_containers):
                # Refresh day containers each iteration (DOM may reload)
                day_containers = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section.card"))
                )
                if day_index >= len(day_containers):
                    print(f"[ERROR] Index {day_index} out of range for day containers. Skipping.")
                    continue

                day_container = day_containers[day_index]
                date_str = day_container.find_element(By.TAG_NAME, "header").text.strip()
                print(f"\n[DEBUG] Processing Day {day_index+1}/{len(day_containers)}: {date_str}")

                # Get all the meal links (Breakfast, Lunch, Dinner, etc.)
                meal_links = day_container.find_elements(By.CSS_SELECTOR, ".cbo_nn_menuLinkCell a")

                # --- Loop through each meal ---
                for meal_index, meal_link in enumerate(meal_links):
                    # Refresh day + meal links since the DOM may change after clicking
                    day_containers_refresh = wait.until(
                        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "section.card"))
                    )

                    if day_index >= len(day_containers_refresh):
                        print(f"[ERROR] Day index {day_index} out of range after refresh. Skipping.")
                        continue

                    meal_links_refresh = day_containers_refresh[day_index].find_elements(
                        By.CSS_SELECTOR, ".cbo_nn_menuLinkCell a"
                    )

                    if meal_index >= len(meal_links_refresh):
                        print(f"⚠️ Skipping: meal index {meal_index} not available for day {day_index}")
                        continue

                    meal_link = meal_links_refresh[meal_index]
                    meal_name = meal_link.text.strip()

                    print(f"  -> Scraping: {date_str} - {meal_name}")
                    safe_click(driver, meal_link, f"meal {meal_name}")

                    try:
                        # Expand all food categories
                        print("      -> Expanding all food categories...")
                        category_dropdowns = wait.until(
                            EC.presence_of_all_elements_located((By.CLASS_NAME, "cbo_nn_itemGroupRow"))
                        )
                        for dropdown in category_dropdowns:
                            safe_click(driver, dropdown, "category dropdown")
                            time.sleep(0.5)

                        # Scrape all visible food items
                        print("      -> Scraping all visible food items...")
                        food_item_links = wait.until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[id^='showNutrition_']"))
                        )
                        num_foods = len(food_item_links)

                        for food_index in range(num_foods):
                            current_food_links = wait.until(
                                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[id^='showNutrition_']"))
                            )
                            food_link = current_food_links[food_index]
                            food_name = food_link.text

                            # Click food item to open nutrition popup
                            safe_click(driver, food_link, f"food item {food_name}")

                            try:
                                print("        > Waiting for nutrition modal...")
                                time.sleep(0.5)

                                # Default values
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

                                nutrient_map = {
                                    'Serving Size': '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[3]/td',
                                    'Calories': '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[5]/td/table/tbody/tr/td[1]/span[2]',
                                    'Total Fat': '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[7]/td/table/tbody/tr/td/table/tbody/tr/td[2]/span',
                                    'Saturated Fat': '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[8]/td/table/tbody/tr/td/table/tbody/tr/td[2]/span',
                                    'Sodium': '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[10]/td/table/tr/td/table/tbody/tr/td[2]/span',
                                    'Total Carbohydrate': '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[11]/td/table/tbody/tr/td/table/tbody/tr/td[2]/span',
                                    'Protein': '//*[@id="nutritionLabel"]/div/div/table/tbody/tr[12]/td/table/tbody/tr/td/table/tbody/tr/td[2]/span'
                                }

                                # Extract nutrients
                                for key, xpath in nutrient_map.items():
                                    try:
                                        value = driver.find_element(By.XPATH, xpath).text
                                        food_details[key] = value
                                        if key == 'Serving Size':
                                            food_details['Serving Size (g)'] = parse_grams(value)
                                    except Exception:
                                        food_details[key] = 'N/A'

                                all_food_data.append(food_details)

                            finally:
                                # Close popup and switch back
                                try:
                                    close_button = driver.find_element(By.CSS_SELECTOR, "#btn_nn_nutrition_close")
                                    safe_click(driver, close_button, "close nutrition modal")
                                    time.sleep(.5)  # let modal disappear
                                except Exception:
                                    pass

                    except TimeoutException:
                        print(f"    No food items found for {meal_name}.")

                    print("    <- Navigating back to weekly menu")
                    try:
                        back_button = wait.until(EC.element_to_be_clickable(
                            (By.XPATH, '//*[@id="itemPanel"]/section/div[1]/nav/a[1]')
                        ))
                        safe_click(driver, back_button, "back button")
                    except TimeoutException:
                        print("      [ERROR] Could not find back button. Skipping...")

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

    column_order = [
        'Date', 'Location', 'Meal', 'Food Name', 'Serving Size (g)', 'Calories',
        'Total Fat', 'Saturated Fat', 'Trans Fat', 'Cholesterol', 'Sodium',
        'Total Carbohydrate', 'Dietary Fiber', 'Sugars', 'Protein', 'Serving Size',
        'Ingredients', 'Calories from Fat', 'Vitamin A', 'Vitamin C', 'Calcium', 'Iron'
    ]

    for col in column_order:
        if col not in df.columns:
            df[col] = 'N/A'

    df = df[column_order]
    df.to_csv('nc_state_dining_menu.csv', index=False, encoding='utf-8')
    print("✅ Success! Data saved to nc_state_dining_menu.csv")


if __name__ == '__main__':
    scrape_ncsu_dining()
