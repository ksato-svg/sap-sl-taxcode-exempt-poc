# Architecture & Processing Flow

## Overview
This PoC updates SAP Business One Sales Orders via Service Layer API, setting blank TaxCode values to "EXEMPT" in document lines.

## Folder Structure
```
sap-sl-taxcode-exempt-poc/
├── src/
│   ├── sap_client.py        # SAP Service Layer API client
│   ├── order_updater.py     # Core business logic
│   └── main.py              # Entry point
├── config/
│   ├── config.json          # Configuration template
│   └── config.local.json    # Local config (gitignored)
├── examples/
│   ├── get_response.json    # Sample GET response
│   └── patch_request.json   # Sample PATCH request
├── logs/
│   └── *.log                # Application logs (gitignored)
└── requirements.txt         # Python dependencies
```

## Processing Flow

### 1. Authentication
```
[Client] -> POST /Login
         <- Session Cookie (B1SESSION, ROUTEID)
```
- Authenticates with SAP Business One Service Layer
- Receives session cookies for subsequent requests
- Cookies stored in session for reuse

### 2. Retrieve Sales Order
```
[Client] -> GET /Orders(DocEntry)
         <- Full Order JSON with DocumentLines
```
- Fetches complete Sales Order document
- Includes all document lines with current TaxCode values
- Returns 404 if DocEntry not found

### 3. Analyze Document Lines
```python
for line in order['DocumentLines']:
    if line.get('TaxCode') in [None, '', ' ']:
        lines_to_update.append(line)
```
- Iterates through all DocumentLines
- Identifies lines with blank/null/empty TaxCode
- Collects line numbers and current state

### 4. Build PATCH Payload (Idempotent)
```
Only include DocumentLines that need updating:
{
    "DocumentLines": [
        {
            "LineNum": <line_number>,
            "TaxCode": "EXEMPT"
        }
    ]
}
```
- Creates minimal PATCH payload
- Only includes lines requiring changes
- Idempotent: re-running won't cause issues

### 5. Update Sales Order
```
[Client] -> PATCH /Orders(DocEntry)
         <- 204 No Content (success)
         <- 400/500 (error)
```
- Sends PATCH with updated lines
- Service Layer merges changes
- Returns 204 on success

### 6. Logging & Results
```
INFO: Processing DocEntry 12345
INFO: Found 3 lines with blank TaxCode
INFO: Lines to update: [0, 2, 5]
INFO: PATCH request successful
INFO: Update completed for DocEntry 12345
```
- Detailed logging at each step
- Success/failure status
- Error details if PATCH fails

## Key Design Decisions

### Idempotency
- Only updates lines where TaxCode is blank
- Safe to re-run multiple times
- Won't overwrite existing non-blank TaxCodes

### Error Handling
- Graceful handling of network errors
- SAP Service Layer error messages logged
- Process continues logging even on failure

### Security
- Configuration file separate from code
- Credentials not hardcoded
- Session cleanup on exit

### Testability
- Fixed DocEntry for initial testing
- Can be extended to batch processing
- Logging provides audit trail

## SAP Service Layer API Notes

### Authentication Endpoint
```
POST https://{server}:{port}/b1s/v1/Login
Content-Type: application/json

{
    "CompanyDB": "SBODEMOUS",
    "UserName": "manager",
    "Password": "password"
}
```

### Orders Endpoint
```
GET    /b1s/v1/Orders(DocEntry)
PATCH  /b1s/v1/Orders(DocEntry)
```

### Important Headers
- `Content-Type: application/json`
- `Cookie: B1SESSION={session}; ROUTEID={route}`
- `Prefer: return=representation` (optional, for response body)

## Extension Points

1. **Batch Processing**: Loop through multiple DocEntries
2. **Filtering**: Query orders by date, status, customer
3. **Validation**: Pre-check TaxCode "EXEMPT" exists in system
4. **Dry-Run Mode**: Preview changes without committing
5. **Rollback**: Store original values for undo capability
