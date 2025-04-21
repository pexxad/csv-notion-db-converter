# このファイルをconfig.pyとしてコピーし、必要な情報を記載してください

NOTION_API_URL = "https://api.notion.com/v1/"
NOTION_API_VERSION = "2022-06-28"
NOTION_API_KEY = "YOUR_NOTION_API_KEY"  # 絶対にcommitしないで！
NOTION_DATABASE_ID = "YOUR_DATABASE_ID"

# CSV列名とNotionプロパティ名・型の対応
CSV_TO_NOTION_MAPPING = {
    "Name": {"notion": "名前", "type": "title"},
    "Group": {"notion": "マルチタグ", "type": "multi_select"},
    "AddressA": {"notion": "Address1", "type": "text"},
    "AddressB": {"notion": "Address2", "type": "text"},
    "Type": {"notion": "単体タグ3", "type": "select"},
    "SpecA": {"notion": "単体タグ1", "type": "select"},
    "SpecB": {"notion": "単体タグ2", "type": "select"},
    # "ValuesJSON": {"notion": "ValuesJSON", "type": "text"},
}

# 複合キーとなるCSV列名のリスト
COMPOSITE_KEY = ["Name", "AddressA", "AddressB"]
