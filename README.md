# csv-notion-db-converter

## sample command output

```
# 登録成功
$ python csv_to_notion.py --csv sample.csv
[OK] Registered: サンプル1::1A2B3C4D::1234567890ABCDEF
[OK] Registered: サンプル2::DEADBEEF::0011223344556677
[OK] Registered: サンプル3::CAFEBABE::FFFFFFFF00000000
完了

# Notion DB登録済でスキップ
$ python csv_to_notion.py --csv sample.csv
[SKIP] Already exists: サンプル1::1A2B3C4D::1234567890ABCDEF
[SKIP] Already exists: サンプル2::DEADBEEF::0011223344556677
[SKIP] Already exists: サンプル3::CAFEBABE::FFFFFFFF00000000
完了

# Notion DBプロパティ名ミスでエラー
$ python csv_to_notion.py --csv sample.csv
[ERR] Failed: サンプル1::1A2B3C4D::1234567890ABCDEF -> {"object":"error","status":400,"code":"validation_error","message":"Group is not a property that exists.","request_id":"0d16d4ed-9cd3-458f-95d8-146ac145511b"}
[ERR] Failed: サンプル2::DEADBEEF::0011223344556677 -> {"object":"error","status":400,"code":"validation_error","message":"Group is not a property that exists.","request_id":"908cb041-0f02-47b0-b86d-4f3cdd860234"}
[ERR] Failed: サンプル3::CAFEBABE::FFFFFFFF00000000 -> {"object":"error","status":400,"code":"validation_error","message":"Group is not a property that exists.","request_id":"88641f3c-d642-46e0-8a57-05e9b20e39a6"}
完了
```
