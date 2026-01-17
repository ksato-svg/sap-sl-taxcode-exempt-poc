# Configuration

## Setup Instructions

1. Copy `config.json` to `config.local.json`:
   ```bash
   cp config.json config.local.json
   ```

2. Edit `config.local.json` with your SAP credentials:
   - `base_url`: Your SAP Service Layer URL
   - `company_db`: Your company database name
   - `username`: SAP B1 username
   - `password`: SAP B1 password
   - `doc_entry`: DocEntry of the Sales Order to update

3. The application will use `config.local.json` if it exists, otherwise falls back to `config.json`

## Security Note

- `config.local.json` is git-ignored to prevent credential leaks
- Never commit credentials to version control
- Use environment variables or secure vaults in production

## Example config.local.json

```json
{
  "sap_service_layer": {
    "base_url": "https://192.168.1.100:50000/b1s/v1",
    "company_db": "SBO_TEST_US",
    "username": "testuser",
    "password": "TestPass123",
    "verify_ssl": false
  },
  "doc_entry": 54321
}
```

## Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| base_url | string | Service Layer API base URL |
| company_db | string | SAP B1 company database identifier |
| username | string | SAP B1 user with order update permissions |
| password | string | User password |
| verify_ssl | boolean | Whether to verify SSL certificates (use false for test) |
| doc_entry | integer | DocEntry of the Sales Order to process |
