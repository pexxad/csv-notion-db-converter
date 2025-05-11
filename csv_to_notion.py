import argparse
import csv
import json
import time
from typing import Any, Dict, List

import requests

import config


def load_csv(csv_path: str, composite_keys: List[str]) -> List[Dict[str, Any]]:
    rows = []
    composite_keys_set = set()
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            composite_key = extract_composite_key(row, composite_keys)
            if composite_key in composite_keys_set:
                raise ValueError(f"CSVファイルに重複する複合キーが存在します: {composite_key}")
            composite_keys_set.add(composite_key)
            rows.append(row)
    return rows


def get_notion_db_items(mapping: Dict[str, Any], composite_keys: List[str]) -> List[Dict[str, Any]]:
    url = f"{config.NOTION_API_URL}/databases/{config.NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {config.NOTION_API_KEY}",
        "Notion-Version": config.NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    results = []
    composite_keys_set = set()
    has_more = True
    next_cursor = None
    while has_more:
        payload = {"page_size": 100}
        if next_cursor:
            payload["start_cursor"] = next_cursor
        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        for page in data.get("results", []):
            composite_key = extract_notion_composite_key(page, mapping, composite_keys)
            if composite_key in composite_keys_set:
                raise ValueError(f"Notionデータベースに重複する複合キーが存在します: {composite_key}")
            composite_keys_set.add(composite_key)
            results.append(page)
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

    return results


def extract_composite_key(row: Dict[str, Any], keys: List[str]) -> str:
    return "::".join([str(row[k]) for k in keys])


def extract_notion_composite_key(page: Dict[str, Any], mapping: Dict[str, Any], keys: List[str]) -> str:
    props = page["properties"]
    values = []
    for csv_key in keys:
        notion_prop = mapping[csv_key]["notion"]
        typ = mapping[csv_key]["type"]
        value = ""
        if typ == "title":
            value = props[notion_prop]["title"][0]["plain_text"] if props[notion_prop]["title"] else ""
        elif typ == "text":
            value = props[notion_prop]["rich_text"][0]["plain_text"] if props[notion_prop]["rich_text"] else ""
        elif typ == "select":
            value = props[notion_prop]["select"]["name"] if props[notion_prop]["select"] else ""
        elif typ == "multi_select":
            value = (
                ",".join([v["name"] for v in props[notion_prop]["multi_select"]])
                if props[notion_prop]["multi_select"]
                else ""
            )
        elif typ == "relation":
            value = (
                ",".join([v["id"] for v in props[notion_prop]["relation"]]) if props[notion_prop]["relation"] else ""
            )
        elif typ == "people":
            value = ",".join([v["id"] for v in props[notion_prop]["people"]]) if props[notion_prop]["people"] else ""
        elif typ == "last_edited_by":
            value = props[notion_prop]["last_edited_by"]["id"] if props[notion_prop]["last_edited_by"] else ""
        elif typ == "last_edited_time":
            value = props[notion_prop]["last_edited_time"] if props[notion_prop]["last_edited_time"] else ""
        values.append(value)
    return "::".join(values)


def filter_new_rows(csv_rows, notion_pages, mapping, composite_keys):
    notion_keys = set([extract_notion_composite_key(page, mapping, composite_keys) for page in notion_pages])
    new_rows = []
    update_rows = []
    for row in csv_rows:
        row_key = extract_composite_key(row, composite_keys)
        if row_key not in notion_keys:
            new_rows.append(row)
        else:
            print(f"[SKIP] Already exists: {row_key}")
            update_rows.append(row)
    return new_rows, update_rows


def make_notion_payload(row: Dict[str, Any], mapping: Dict[str, Any]) -> Dict[str, Any]:
    props = {}
    for csv_col, mapinfo in mapping.items():
        notion_prop = mapinfo["notion"]
        typ = mapinfo["type"]
        value = row[csv_col]
        if typ == "title":
            props[notion_prop] = {"title": [{"text": {"content": value}}]}
        elif typ == "text":
            props[notion_prop] = {"rich_text": [{"text": {"content": value}}]}
        elif typ == "select":
            if value:
                props[notion_prop] = {"select": {"name": value}}
            else:
                props[notion_prop] = {"select": None}
        elif typ == "multi_select":
            # カンマ区切りで複数値を受け取る前提
            values = [v.strip() for v in value.split(",") if v.strip()]
            props[notion_prop] = {"multi_select": [{"name": v} for v in values]}
        elif typ == "relation":
            # カンマ区切りでNotionのページIDを受け取る前提
            ids = [v.strip() for v in value.split(",") if v.strip()]
            props[notion_prop] = {"relation": [{"id": v} for v in ids]}
        elif typ == "people":
            # カンマ区切りでユーザーIDを受け取る前提
            ids = [v.strip() for v in value.split(",") if v.strip()]
            props[notion_prop] = {"people": [{"id": v} for v in ids]}
        elif typ == "last_edited_by":
            # 通常自動。明示的に指定したい場合のみ
            if value:
                props[notion_prop] = {"last_edited_by": {"id": value}}
        elif typ == "last_edited_time":
            # 通常自動。明示的に指定したい場合のみ
            if value:
                props[notion_prop] = {"last_edited_time": value}
    return {"parent": {"database_id": config.NOTION_DATABASE_ID}, "properties": props}


def register_to_notion(rows: List[Dict[str, Any]], mapping: Dict[str, Any]):
    url = f"{config.NOTION_API_URL}/pages"
    headers = {
        "Authorization": f"Bearer {config.NOTION_API_KEY}",
        "Notion-Version": config.NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    for row in rows:
        payload = make_notion_payload(row, mapping)
        while True:
            resp = requests.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                print(f"[OK] Registered: {extract_composite_key(row, config.COMPOSITE_KEY)}")
                break
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 1))
                print(f"[WARN] Rate limited. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
            else:
                print(f"[ERR] Failed: {extract_composite_key(row, config.COMPOSITE_KEY)} -> {resp.text}")
                break


def update_notion(
    update_rows: List[Dict[str, Any]],
    notion_pages: List[Dict[str, Any]],
    mapping: Dict[str, Any],
    composite_keys: List[str],
):
    url = f"{config.NOTION_API_URL}/pages"
    headers = {
        "Authorization": f"Bearer {config.NOTION_API_KEY}",
        "Notion-Version": config.NOTION_API_VERSION,
        "Content-Type": "application/json",
    }
    for row in update_rows:
        row_key = extract_composite_key(row, composite_keys)
        # NotionのページIDを取得
        page_id = None
        for page in notion_pages:
            if extract_notion_composite_key(page, mapping, composite_keys) == row_key:
                page_id = page["id"]
                break
        if not page_id:
            print(f"[ERR] Page ID not found: {row_key}")
            continue

        payload = make_notion_payload(row, mapping)
        while True:
            resp = requests.patch(f"{url}/{page_id}", headers=headers, json=payload)
            if resp.status_code == 200:
                print(f"[OK] Updated: {row_key}")
                break
            elif resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 1))
                print(f"[WARN] Rate limited. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
            else:
                print(f"[ERR] Failed to update: {row_key} -> {resp.text}")
                break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="CSVファイルのパス")
    parser.add_argument("--dryrun", action="store_true", help="ドライランオプション")
    args = parser.parse_args()

    # 設定バリデーション
    assert config.NOTION_API_URL and config.NOTION_API_KEY and config.NOTION_DATABASE_ID
    assert isinstance(config.CSV_TO_NOTION_MAPPING, dict)
    assert isinstance(config.COMPOSITE_KEY, list)

    csv_rows = load_csv(args.csv, config.COMPOSITE_KEY)
    notion_pages = get_notion_db_items(config.CSV_TO_NOTION_MAPPING, config.COMPOSITE_KEY)
    new_rows, update_rows = filter_new_rows(csv_rows, notion_pages, config.CSV_TO_NOTION_MAPPING, config.COMPOSITE_KEY)
    if not args.dryrun:
        register_to_notion(new_rows, config.CSV_TO_NOTION_MAPPING)
        update_notion(update_rows, notion_pages, config.CSV_TO_NOTION_MAPPING, config.COMPOSITE_KEY)
    else:
        print("ドライランモードのため、Notion APIへの登録はスキップします")
    print("完了")


if __name__ == "__main__":
    main()
