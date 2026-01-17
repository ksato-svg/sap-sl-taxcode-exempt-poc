# Sample Payloads

## get_response.json
Sample response from `GET /Orders(12345)` showing a Sales Order with 5 document lines.

**Lines requiring update:**
- Line 0: TaxCode is empty string `""`
- Line 2: TaxCode is null
- Line 4: TaxCode is whitespace `" "`

**Lines already correct:**
- Line 1: TaxCode is "VAT10" (has value, skip)
- Line 3: TaxCode is "EXEMPT" (already correct, skip)

## patch_request.json
Minimal PATCH payload to update only the lines with blank TaxCode.

**Key points:**
- Only includes `LineNum` and `TaxCode` fields
- Only includes lines that need updating (idempotent)
- Lines 1 and 3 are not included (already have valid TaxCode)

**Usage:**
```
PATCH https://sapserver:50000/b1s/v1/Orders(12345)
Content-Type: application/json
Cookie: B1SESSION=...; ROUTEID=...

{body from patch_request.json}
```

**Expected Response:**
- Success: `204 No Content`
- Error: `400 Bad Request` or `500 Internal Server Error` with error details
