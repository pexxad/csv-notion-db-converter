import argparse
import csv
import json
import requests
from config import Config


def validate_config():
    """Validates the Notion configuration from config.py."""
    if not Config.API_KEY or Config.API_KEY == "YOUR_NOTION_API_KEY_HERE":
        print("Error: Config.API_KEY is not set or is a placeholder in 'config.py'.")
        print("Please replace 'YOUR_NOTION_API_KEY_HERE' with your actual Notion API key.")
        exit(1)
    if not Config.DATABASE_ID or Config.DATABASE_ID == "YOUR_NOTION_DATABASE_ID_HERE":
        print("Error: Config.DATABASE_ID is not set or is a placeholder in 'config.py'.")
        print("Please replace 'YOUR_NOTION_DATABASE_ID_HERE' with your actual Notion Database ID.")
        exit(1)
    # API_URL has a default, API_VERSION is assumed to be set correctly in config.py
    if not Config.API_VERSION:
        print("Error: Config.API_VERSION is not set in 'config.py'.")
        exit(1)


def get_notion_headers():
    """Returns the headers required for Notion API requests using config.py."""
    return {
        "Authorization": f"Bearer {Config.API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": Config.API_VERSION,
    }


def get_database_schema():
    """Retrieves the schema (properties) of the Notion database using config.py."""
    url = f"{Config.API_URL}/databases/{Config.DATABASE_ID}"
    headers = get_notion_headers()
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        return response.json()["properties"]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching database schema: {e}")
        if response is not None:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
        exit(1)
    except KeyError:
        print("Error: Could not parse 'properties' from database schema response.")
        print(f"Response body: {response.text}")
        exit(1)


# --- CSV Handling ---


def read_csv(file_path):
    """Reads data from a CSV file."""
    data = []
    try:
        with open(file_path, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            if not reader.fieldnames:
                print(f"Error: CSV file '{file_path}' is empty or has no header row.")
                return None, None
            for row in reader:
                data.append(row)
        return reader.fieldnames, data
    except FileNotFoundError:
        print(f"Error: Input CSV file '{file_path}' not found.")
        exit(1)
    except Exception as e:
        print(f"Error reading CSV file '{file_path}': {e}")
        exit(1)


def write_csv(file_path, headers, data):
    """Writes data to a CSV file."""
    try:
        with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            writer.writerows(data)
        print(f"Successfully wrote data to '{file_path}'")
    except Exception as e:
        print(f"Error writing CSV file '{file_path}': {e}")
        exit(1)


# --- Conversion Logic ---


def convert_csv_row_to_notion_properties(csv_row, db_properties):
    """Converts a CSV row (dict) to Notion API properties format."""
    properties = {}
    for prop_name, prop_details in db_properties.items():
        prop_type = prop_details["type"]
        csv_value = csv_row.get(prop_name)  # Get value from CSV, default None if missing

        if csv_value is None:
            continue  # Skip if column doesn't exist in CSV

        # Basic type handling - needs expansion for specific Notion types
        if prop_type == "title":
            properties[prop_name] = {"title": [{"text": {"content": csv_value}}]}
        elif prop_type == "rich_text":
            properties[prop_name] = {"rich_text": [{"text": {"content": csv_value}}]}
        elif prop_type == "number":
            try:
                # Attempt to convert to float, handle potential errors
                number_value = float(csv_value) if csv_value else None
                if number_value is not None:
                    properties[prop_name] = {"number": number_value}
            except ValueError:
                print(f"Warning: Could not convert '{csv_value}' to number for property '{prop_name}'. Skipping.")
        elif prop_type == "select":
            if csv_value:  # Only add if there's a value
                properties[prop_name] = {"select": {"name": csv_value}}
        elif prop_type == "multi_select":
            if csv_value:
                # Assuming multi-select values in CSV are comma-separated
                names = [name.strip() for name in csv_value.split(",")]
                properties[prop_name] = {"multi_select": [{"name": name} for name in names]}
        elif prop_type == "date":
            if csv_value:  # Assuming YYYY-MM-DD format
                properties[prop_name] = {"date": {"start": csv_value}}
        elif prop_type == "checkbox":
            # Assuming 'TRUE', 'true', '1' for checked, others unchecked
            is_checked = csv_value.lower() in ["true", "1"]
            properties[prop_name] = {"checkbox": is_checked}
        elif prop_type == "url":
            if csv_value:
                properties[prop_name] = {"url": csv_value}
        elif prop_type == "email":
            if csv_value:
                properties[prop_name] = {"email": csv_value}
        elif prop_type == "phone_number":
            if csv_value:
                properties[prop_name] = {"phone_number": csv_value}
        # Add more type conversions as needed (files, relation, rollup, etc.)
        else:
            print(f"Warning: Unsupported property type '{prop_type}' for '{prop_name}'. Skipping.")

    return properties


def add_row_to_notion(properties):
    """Adds a single row (page) to the Notion database using config.py."""
    url = f"{Config.API_URL}/pages"
    headers = get_notion_headers()
    payload = {
        "parent": {"database_id": Config.DATABASE_ID},
        "properties": properties,
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        print(f"Successfully added row: {list(properties.keys())}")  # Log which properties were added
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error adding row to Notion: {e}")
        if response is not None:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
            # Provide more specific feedback based on common errors
            if response.status_code == 400:
                print("Hint: Check if property types/values match the Notion database schema.")
            elif response.status_code == 401:
                print("Hint: Check if your Notion API key is correct and has permissions.")
            elif response.status_code == 404:
                print("Hint: Check if the Database ID is correct.")
        return None  # Indicate failure


def csv_to_notion(csv_path):
    """Reads a CSV and uploads its content to a Notion database."""
    print(f"Starting CSV to Notion conversion for '{csv_path}'...")
    db_properties = get_database_schema()
    if not db_properties:
        return  # Error handled in get_database_schema

    print(f"Database Schema Properties: {list(db_properties.keys())}")

    csv_headers, csv_data = read_csv(csv_path)
    if not csv_data:
        return  # Error handled in read_csv

    print(f"Found {len(csv_data)} rows in CSV.")

    added_count = 0
    for i, row in enumerate(csv_data):
        print(f"\nProcessing CSV row {i+1}...")
        notion_properties = convert_csv_row_to_notion_properties(row, db_properties)
        if not notion_properties:
            print(f"Warning: No properties generated for row {i+1}. Skipping.")
            continue

        print(
            f"Converted properties: {json.dumps(notion_properties, indent=2)}"
        )  # Log converted properties before sending

        result = add_row_to_notion(notion_properties)
        if result:
            added_count += 1
        else:
            print(f"Failed to add row {i+1}. See error details above.")
            # Optionally add a flag to stop on first error

    print(f"\nConversion finished. Successfully added {added_count}/{len(csv_data)} rows to Notion.")


def convert_notion_page_to_csv_row(notion_page, csv_headers):
    """Converts a Notion page object to a dictionary for CSV writing."""
    row = {header: None for header in csv_headers}  # Initialize with None
    properties = notion_page.get("properties", {})

    for prop_name, prop_details in properties.items():
        if prop_name not in csv_headers:
            continue  # Skip properties not in the desired CSV headers

        prop_type = prop_details["type"]
        value = None

        # Extract value based on type - needs expansion
        if prop_type == "title" and prop_details.get("title"):
            value = prop_details["title"][0]["plain_text"] if prop_details["title"] else ""
        elif prop_type == "rich_text" and prop_details.get("rich_text"):
            value = prop_details["rich_text"][0]["plain_text"] if prop_details["rich_text"] else ""
        elif prop_type == "number":
            value = prop_details.get("number")
        elif prop_type == "select" and prop_details.get("select"):
            value = prop_details["select"]["name"]
        elif prop_type == "multi_select" and prop_details.get("multi_select"):
            value = ",".join([item["name"] for item in prop_details["multi_select"]])
        elif prop_type == "date" and prop_details.get("date"):
            value = prop_details["date"]["start"]  # Assuming only start date for now
        elif prop_type == "checkbox":
            value = prop_details.get("checkbox")
        elif prop_type == "url":
            value = prop_details.get("url")
        elif prop_type == "email":
            value = prop_details.get("email")
        elif prop_type == "phone_number":
            value = prop_details.get("phone_number")
        elif prop_type == "formula" and prop_details.get("formula"):
            formula_result = prop_details["formula"]
            formula_type = formula_result["type"]
            if formula_type == "string":
                value = formula_result["string"]
            elif formula_type == "number":
                value = formula_result["number"]
            elif formula_type == "boolean":
                value = formula_result["boolean"]
            elif formula_type == "date":
                value = formula_result["date"]["start"] if formula_result.get("date") else None
            # Add other formula result types if needed
        elif prop_type == "relation" and prop_details.get("relation"):
            # Just list related page IDs for now
            value = ",".join([item["id"] for item in prop_details["relation"]])
        elif prop_type == "rollup" and prop_details.get("rollup"):
            rollup_result = prop_details["rollup"]
            rollup_type = rollup_result["type"]
            # Extract rollup value based on its type (number, date, array, etc.)
            if rollup_type == "number":
                value = rollup_result.get("number")
            elif rollup_type == "date":
                value = rollup_result.get("date", {}).get("start")
            elif rollup_type == "array":  # Often seen with relations/multi-select rollups
                # Extract values from the array items based on their type
                array_values = []
                for item in rollup_result.get("array", []):
                    item_type = item.get("type")
                    if item_type == "title":
                        array_values.append(item["title"][0]["plain_text"] if item.get("title") else "")
                    elif item_type == "rich_text":
                        array_values.append(item["rich_text"][0]["plain_text"] if item.get("rich_text") else "")
                    # Add other types within rollup arrays as needed
                value = ",".join(filter(None, array_values))  # Join non-empty strings
            else:
                print(f"Warning: Unsupported rollup result type '{rollup_type}' for '{prop_name}'.")
        # Add more type extractions as needed (files, created_time, etc.)
        else:
            # Silently ignore unsupported types for now, or add a warning
            # print(f"Warning: Unsupported property type '{prop_type}' for '{prop_name}' during Notion->CSV conversion.")
            pass

        row[prop_name] = value

    return row


def get_all_notion_pages():
    """Retrieves all pages (rows) from the Notion database with pagination."""
    all_pages = []
    url = f"{Config.API_URL}/databases/{Config.DATABASE_ID}/query"
    headers = get_notion_headers()
    has_more = True
    next_cursor = None

    print("Fetching data from Notion database...")
    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

            all_pages.extend(data.get("results", []))
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
            print(f"Fetched {len(data.get('results', []))} pages. Total: {len(all_pages)}. Has more: {has_more}")

        except requests.exceptions.RequestException as e:
            print(f"Error fetching pages from Notion: {e}")
            if response is not None:
                print(f"Response status: {response.status_code}")
                print(f"Response body: {response.text}")
            exit(1)
        except KeyError as e:
            print(f"Error parsing Notion response: Missing key {e}")
            print(f"Response body: {response.text}")
            exit(1)

    print(f"Finished fetching. Total pages retrieved: {len(all_pages)}")
    return all_pages


def notion_to_csv(csv_path):
    """Fetches data from a Notion database and writes it to a CSV file."""
    print(f"Starting Notion to CSV conversion to '{csv_path}'...")
    # 1. Get Database Schema to determine headers
    db_properties = get_database_schema()
    if not db_properties:
        return  # Error handled in get_database_schema
    # Use property names as CSV headers
    csv_headers = list(db_properties.keys())
    print(f"Using database properties as CSV headers: {csv_headers}")

    # 2. Get all pages from the database
    notion_pages = get_all_notion_pages()
    if not notion_pages:
        print("No pages found in the Notion database or error fetching.")
        # Create an empty CSV with headers if requested
        write_csv(csv_path, csv_headers, [])
        return

    # 3. Convert each page to a CSV row dictionary
    csv_data = []
    for page in notion_pages:
        csv_row = convert_notion_page_to_csv_row(page, csv_headers)
        csv_data.append(csv_row)

    # 4. Write data to CSV
    write_csv(csv_path, csv_headers, csv_data)


# --- Main Execution ---

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert between CSV files and Notion databases.")
    parser.add_argument(
        "mode",
        choices=["csv_to_notion", "notion_to_csv"],
        help="Conversion direction: 'csv_to_notion' or 'notion_to_csv'",
    )
    parser.add_argument(
        "--input",
        "-i",
        required=False,
        help="Path to the input CSV file (required for csv_to_notion)",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=False,
        help="Path to the output CSV file (required for notion_to_csv)",
    )
    args = parser.parse_args()

    # Validate input/output based on mode
    if args.mode == "csv_to_notion" and not args.input:
        parser.error("--input is required for mode 'csv_to_notion'")
    if args.mode == "notion_to_csv" and not args.output:
        parser.error("--output is required for mode 'notion_to_csv'")

    # Validate configuration
    validate_config()

    # Execute the chosen conversion mode
    if args.mode == "csv_to_notion":
        csv_to_notion(args.input)
    elif args.mode == "notion_to_csv":
        notion_to_csv(args.output)

    print("\nDone.")
