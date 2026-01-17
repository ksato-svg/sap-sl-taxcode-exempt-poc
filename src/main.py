"""
Main entry point for SAP Tax Code Exempt PoC.
Updates Sales Orders to set blank TaxCodes to EXEMPT.
"""

import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from sap_client import SAPServiceLayerClient
from order_updater import OrderTaxCodeUpdater


def setup_logging(log_dir: Path) -> None:
    """
    Configure logging to both file and console.

    Args:
        log_dir: Directory for log files
    """
    log_dir.mkdir(exist_ok=True)

    # Create log filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f"taxcode_update_{timestamp}.log"

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file}")


def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    logger = logging.getLogger(__name__)

    if not config_path.exists():
        logger.error(f"Configuration file not found: {config_path}")
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    logger.info(f"Configuration loaded from {config_path}")
    return config


def main():
    """Main execution function."""
    # Setup paths
    project_root = Path(__file__).parent.parent
    log_dir = project_root / "logs"
    config_dir = project_root / "config"

    # Initialize logging
    setup_logging(log_dir)
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("SAP Business One - TaxCode EXEMPT Update PoC")
    logger.info("=" * 80)

    try:
        # Load configuration (prefer local config, fallback to default)
        config_local = config_dir / "config.local.json"
        config_default = config_dir / "config.json"

        config_path = config_local if config_local.exists() else config_default
        config = load_config(config_path)

        # Extract configuration
        sap_config = config.get('sap_service_layer', {})
        doc_entry = config.get('doc_entry')

        if not doc_entry:
            logger.error("doc_entry not specified in configuration")
            return 1

        # Initialize SAP client
        client = SAPServiceLayerClient(
            base_url=sap_config.get('base_url'),
            company_db=sap_config.get('company_db'),
            username=sap_config.get('username'),
            password=sap_config.get('password'),
            verify_ssl=sap_config.get('verify_ssl', False)
        )

        # Use context manager for automatic login/logout
        with client:
            logger.info(f"Starting update process for DocEntry: {doc_entry}")

            # Step 1: Retrieve order
            order_data = client.get_order(doc_entry)
            if not order_data:
                logger.error(f"Failed to retrieve order {doc_entry}")
                return 1

            # Step 2: Analyze and prepare update
            needs_update, patch_payload = OrderTaxCodeUpdater.process_order(order_data)

            if not needs_update:
                logger.info("✓ No updates required - all TaxCodes already set")
                return 0

            # Step 3: Perform update
            logger.info("Executing PATCH request...")
            success = client.update_order(doc_entry, patch_payload)

            if success:
                logger.info("=" * 80)
                logger.info("✓ UPDATE SUCCESSFUL")
                logger.info(f"  DocEntry {doc_entry} has been updated")
                logger.info(f"  Blank TaxCodes set to: {OrderTaxCodeUpdater.TARGET_TAX_CODE}")
                logger.info("=" * 80)
                return 0
            else:
                logger.error("=" * 80)
                logger.error("✗ UPDATE FAILED")
                logger.error(f"  DocEntry {doc_entry} could not be updated")
                logger.error("  Check logs above for error details")
                logger.error("=" * 80)
                return 1

    except FileNotFoundError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except KeyError as e:
        logger.error(f"Missing configuration key: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
