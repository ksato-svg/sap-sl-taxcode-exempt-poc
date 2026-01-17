"""
Sales Order TaxCode Updater
Core business logic for updating blank TaxCodes to EXEMPT.
"""

import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


class OrderTaxCodeUpdater:
    """Updates blank TaxCodes in Sales Order document lines."""

    TARGET_TAX_CODE = "EXEMPT"

    @staticmethod
    def is_blank_taxcode(tax_code: Any) -> bool:
        """
        Check if a TaxCode value is considered blank.

        Args:
            tax_code: The TaxCode value to check

        Returns:
            True if blank (None, empty string, or whitespace only)
        """
        if tax_code is None:
            return True
        if isinstance(tax_code, str) and tax_code.strip() == "":
            return True
        return False

    @classmethod
    def analyze_order(cls, order_data: Dict[str, Any]) -> Tuple[List[int], List[Dict[str, Any]]]:
        """
        Analyze order to find lines with blank TaxCode.

        Args:
            order_data: Full order data from GET request

        Returns:
            Tuple of (line_numbers_to_update, line_details)
        """
        doc_lines = order_data.get('DocumentLines', [])
        lines_to_update = []
        line_details = []

        logger.info(f"Analyzing {len(doc_lines)} document lines")

        for line in doc_lines:
            line_num = line.get('LineNum')
            tax_code = line.get('TaxCode')
            item_code = line.get('ItemCode', 'N/A')

            if cls.is_blank_taxcode(tax_code):
                lines_to_update.append(line_num)
                line_details.append({
                    'LineNum': line_num,
                    'ItemCode': item_code,
                    'CurrentTaxCode': repr(tax_code),
                    'ItemDescription': line.get('ItemDescription', 'N/A')
                })
                logger.info(f"  Line {line_num} (Item: {item_code}): TaxCode is blank ({repr(tax_code)})")
            else:
                logger.debug(f"  Line {line_num} (Item: {item_code}): TaxCode is '{tax_code}' - skipping")

        logger.info(f"Found {len(lines_to_update)} lines with blank TaxCode: {lines_to_update}")
        return lines_to_update, line_details

    @classmethod
    def build_patch_payload(cls, line_numbers: List[int]) -> Dict[str, Any]:
        """
        Build PATCH payload for updating TaxCodes.

        Args:
            line_numbers: List of line numbers to update

        Returns:
            Dictionary ready for PATCH request
        """
        if not line_numbers:
            return {"DocumentLines": []}

        document_lines = [
            {
                "LineNum": line_num,
                "TaxCode": cls.TARGET_TAX_CODE
            }
            for line_num in line_numbers
        ]

        payload = {"DocumentLines": document_lines}
        logger.info(f"Built PATCH payload for {len(line_numbers)} lines")
        logger.debug(f"PATCH payload: {payload}")

        return payload

    @classmethod
    def process_order(cls, order_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Process an order to update blank TaxCodes.

        Args:
            order_data: Full order data from GET request

        Returns:
            Tuple of (needs_update, patch_payload)
            - needs_update: True if there are lines to update
            - patch_payload: The payload for PATCH request
        """
        doc_entry = order_data.get('DocEntry')
        doc_num = order_data.get('DocNum')

        logger.info(f"Processing Order - DocEntry: {doc_entry}, DocNum: {doc_num}")

        # Analyze order
        line_numbers, line_details = cls.analyze_order(order_data)

        # Check if update needed
        if not line_numbers:
            logger.info("No lines require updating (all TaxCodes already set)")
            return False, {}

        # Build patch payload
        patch_payload = cls.build_patch_payload(line_numbers)

        # Log summary
        logger.info("=" * 60)
        logger.info("UPDATE SUMMARY:")
        logger.info(f"  DocEntry: {doc_entry}")
        logger.info(f"  DocNum: {doc_num}")
        logger.info(f"  Lines to update: {len(line_numbers)}")
        for detail in line_details:
            logger.info(f"    - Line {detail['LineNum']}: {detail['ItemCode']} ({detail['ItemDescription']})")
            logger.info(f"      Current: {detail['CurrentTaxCode']} -> New: {cls.TARGET_TAX_CODE}")
        logger.info("=" * 60)

        return True, patch_payload
