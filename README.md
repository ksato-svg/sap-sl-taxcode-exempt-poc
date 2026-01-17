# SAP Business One - TaxCode EXEMPT Update PoC

Proof-of-Concept for updating SAP Business One Sales Orders via Service Layer API.
Sets blank TaxCode values to "EXEMPT" in document lines.

## Features

- Connects to SAP Business One Service Layer API
- Retrieves Sales Orders by DocEntry
- Identifies document lines with blank TaxCode (null, empty string, or whitespace)
- Updates only blank lines to "EXEMPT" (idempotent)
- Comprehensive logging to file and console
- Secure configuration management

## Project Structure

```
sap-sl-taxcode-exempt-poc/
├── src/
│   ├── main.py              # Entry point
│   ├── sap_client.py        # Service Layer API client
│   └── order_updater.py     # Business logic
├── config/
│   ├── config.json          # Configuration template
│   └── config.local.json    # Local config (gitignored)
├── examples/
│   ├── get_response.json    # Sample GET response
│   ├── patch_request.json   # Sample PATCH request
│   └── README.md            # Payload documentation
├── logs/
│   └── *.log                # Application logs (gitignored)
├── requirements.txt         # Python dependencies
└── ARCHITECTURE.md          # Detailed architecture docs
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure SAP Connection

Create local configuration file:

```bash
cp config/config.json config/config.local.json
```

Edit `config/config.local.json` with your SAP credentials:

```json
{
  "sap_service_layer": {
    "base_url": "https://your-sap-server:50000/b1s/v1",
    "company_db": "YOUR_COMPANY_DB",
    "username": "your-username",
    "password": "your-password",
    "verify_ssl": false
  },
  "doc_entry": 12345
}
```

## Usage

### Run the Update

```bash
cd src
python main.py
```

### Expected Output

```
2024-01-15 10:30:00 - __main__ - INFO - ================================================================================
2024-01-15 10:30:00 - __main__ - INFO - SAP Business One - TaxCode EXEMPT Update PoC
2024-01-15 10:30:00 - __main__ - INFO - ================================================================================
2024-01-15 10:30:01 - sap_client - INFO - Authenticating to SAP B1 (Company: SBODEMOUS, User: manager)
2024-01-15 10:30:02 - sap_client - INFO - Authentication successful. SessionId: abc123...
2024-01-15 10:30:02 - sap_client - INFO - Fetching Sales Order DocEntry: 12345
2024-01-15 10:30:03 - sap_client - INFO - Retrieved Sales Order 12345 successfully (5 lines)
2024-01-15 10:30:03 - order_updater - INFO - Processing Order - DocEntry: 12345, DocNum: 10001
2024-01-15 10:30:03 - order_updater - INFO - Analyzing 5 document lines
2024-01-15 10:30:03 - order_updater - INFO -   Line 0 (Item: ITEM001): TaxCode is blank ('')
2024-01-15 10:30:03 - order_updater - INFO -   Line 2 (Item: ITEM003): TaxCode is blank (None)
2024-01-15 10:30:03 - order_updater - INFO -   Line 4 (Item: ITEM005): TaxCode is blank (' ')
2024-01-15 10:30:03 - order_updater - INFO - Found 3 lines with blank TaxCode: [0, 2, 4]
2024-01-15 10:30:03 - order_updater - INFO - ============================================================
2024-01-15 10:30:03 - order_updater - INFO - UPDATE SUMMARY:
2024-01-15 10:30:03 - order_updater - INFO -   DocEntry: 12345
2024-01-15 10:30:03 - order_updater - INFO -   DocNum: 10001
2024-01-15 10:30:03 - order_updater - INFO -   Lines to update: 3
2024-01-15 10:30:03 - order_updater - INFO -     - Line 0: ITEM001 (Product A)
2024-01-15 10:30:03 - order_updater - INFO -       Current: '' -> New: EXEMPT
2024-01-15 10:30:03 - order_updater - INFO -     - Line 2: ITEM003 (Product C)
2024-01-15 10:30:03 - order_updater - INFO -       Current: None -> New: EXEMPT
2024-01-15 10:30:03 - order_updater - INFO -     - Line 4: ITEM005 (Product E)
2024-01-15 10:30:03 - order_updater - INFO -       Current: ' ' -> New: EXEMPT
2024-01-15 10:30:03 - order_updater - INFO - ============================================================
2024-01-15 10:30:03 - sap_client - INFO - Updating Sales Order DocEntry: 12345
2024-01-15 10:30:04 - sap_client - INFO - Sales Order 12345 updated successfully
2024-01-15 10:30:04 - __main__ - INFO - ================================================================================
2024-01-15 10:30:04 - __main__ - INFO - ✓ UPDATE SUCCESSFUL
2024-01-15 10:30:04 - __main__ - INFO -   DocEntry 12345 has been updated
2024-01-15 10:30:04 - __main__ - INFO -   Blank TaxCodes set to: EXEMPT
2024-01-15 10:30:04 - __main__ - INFO - ================================================================================
```

## How It Works

1. **Authentication**: Logs into SAP Service Layer with credentials
2. **Retrieve Order**: Fetches Sales Order by DocEntry via GET request
3. **Analyze Lines**: Identifies document lines with blank TaxCode
4. **Build Payload**: Creates minimal PATCH payload with only lines needing update
5. **Update Order**: Sends PATCH request to update TaxCodes
6. **Log Results**: Outputs detailed success/failure information

## Idempotency

The script is designed to be idempotent:
- Only updates lines where TaxCode is blank (null, empty, or whitespace)
- Safe to run multiple times
- Won't overwrite existing non-blank TaxCodes
- If all lines already have TaxCode set, no PATCH is performed

## Logs

All operations are logged to:
- **Console**: Real-time output
- **File**: `logs/taxcode_update_YYYYMMDD_HHMMSS.log`

Logs include:
- Authentication status
- Order retrieval details
- Lines requiring update
- PATCH request payload
- Success/failure status
- Error messages

## Testing

1. Start with a test Sales Order that has some blank TaxCodes
2. Set the `doc_entry` in config to this test order
3. Run the script
4. Verify in SAP B1 that blank TaxCodes are now "EXEMPT"
5. Run again to verify idempotency (should report no updates needed)

## Troubleshooting

### Authentication Failed
- Verify `base_url`, `company_db`, `username`, and `password`
- Check network connectivity to SAP server
- Ensure user has permissions to access Service Layer

### Order Not Found
- Verify `doc_entry` exists in the system
- Check that the order is a Sales Order (not other document type)
- Ensure user has permission to view this order

### Update Failed
- Check if order is already closed or canceled
- Verify "EXEMPT" is a valid TaxCode in your SAP system
- Review error message in logs for specific SAP error details

### SSL Certificate Errors
- For test environments, set `verify_ssl: false`
- For production, install proper SSL certificates or use `verify_ssl: true`

## Security Notes

- Never commit `config.local.json` to version control
- Store credentials securely (environment variables, vaults)
- Use HTTPS for Service Layer communication
- Restrict user permissions to minimum required

## Future Enhancements

- Batch processing for multiple DocEntries
- Filter orders by date range or status
- Configurable target TaxCode (not just "EXEMPT")
- Dry-run mode to preview changes
- Rollback capability
- Email notifications on completion

## Documentation

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed processing flow and design decisions.

See [examples/](examples/) for sample API payloads.

## License

PoC for internal use only.
