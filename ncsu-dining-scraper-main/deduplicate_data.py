import pandas as pd
import os
import json

# Configuration
FRESH_DATA_FILE = 'nc_state_dining_menu.csv'
HISTORY_FILE = 'upload_history.json'
UPLOAD_QUEUE_FILE = 'to_upload.csv'

def deduplicate():
    # 1. Load the fresh scrape
    if not os.path.exists(FRESH_DATA_FILE):
        print(f" Error: {FRESH_DATA_FILE} not found. Run the scraper first.")
        return

    df = pd.read_csv(FRESH_DATA_FILE)
    print(f" Loaded {len(df)} items from the latest scrape.")

    # 2. Load (or create) the history file
    # The history file stores unique IDs of foods we've already seen.
    # We'll use "Food Name + Calories" as a unique signature.
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
        print(f" Loaded history: {len(history)} items previously processed.")
    else:
        history = []
        print(" No history found. Creating a new history file.")

    # 3. Filter for NEW items
    new_items = []
    
    # We convert the list to a set for instant O(1) lookups
    history_set = set(history)

    for index, row in df.iterrows():
        # Create a unique signature for this food
        # Example: "Buttermilk Biscuit_190"
        # This allows for different versions of the same food if macros change
        unique_id = f"{row['Food Name']}_{row['Calories']}"

        if unique_id not in history_set:
            new_items.append(row)
            # Add to temporary set so we don't add duplicates from the *current* scrape
            # (e.g. if 'Buttermilk Biscuit' appears on Monday AND Tuesday menu)
            history_set.add(unique_id) 

    # 4. Save the queue
    if new_items:
        queue_df = pd.DataFrame(new_items)
        queue_df.to_csv(UPLOAD_QUEUE_FILE, index=False)
        print(f"\n Success! Found {len(new_items)} new items.")
        print(f" Saved to '{UPLOAD_QUEUE_FILE}' - These are ready for upload.")
        
        # NOTE: We do NOT update the history.json yet. 
        # We only update history after the Uploader Bot confirms success.
    else:
        print("\n No new items found. You are up to date")
        # Create an empty file just so the next script doesn't crash
        pd.DataFrame(columns=df.columns).to_csv(UPLOAD_QUEUE_FILE, index=False)

if __name__ == "__main__":
    deduplicate()