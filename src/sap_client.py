"""
SAP Business One Service Layer API Client
Handles authentication and HTTP requests to the Service Layer.
"""

import requests
import logging
from typing import Optional, Dict, Any
import urllib3

# Disable SSL warnings for test environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class SAPServiceLayerClient:
    """Client for interacting with SAP Business One Service Layer API."""

    def __init__(self, base_url: str, company_db: str, username: str, password: str, verify_ssl: bool = False):
        """
        Initialize SAP Service Layer client.

        Args:
            base_url: Base URL of Service Layer (e.g., https://server:50000/b1s/v1)
            company_db: Company database name
            username: SAP B1 username
            password: SAP B1 password
            verify_ssl: Whether to verify SSL certificates (False for test environments)
        """
        self.base_url = base_url.rstrip('/')
        self.company_db = company_db
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self._authenticated = False

        logger.info(f"Initialized SAP client for {base_url}")

    def login(self) -> bool:
        """
        Authenticate with SAP Service Layer.

        Returns:
            True if authentication successful, False otherwise
        """
        login_url = f"{self.base_url}/Login"
        payload = {
            "CompanyDB": self.company_db,
            "UserName": self.username,
            "Password": self.password
        }

        try:
            logger.info(f"Authenticating to SAP B1 (Company: {self.company_db}, User: {self.username})")
            response = self.session.post(login_url, json=payload, timeout=30)

            if response.status_code == 200:
                session_data = response.json()
                logger.info(f"Authentication successful. SessionId: {session_data.get('SessionId', 'N/A')}")
                self._authenticated = True
                return True
            else:
                logger.error(f"Authentication failed. Status: {response.status_code}, Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Authentication error: {str(e)}")
            return False

    def logout(self) -> None:
        """Logout from SAP Service Layer."""
        if not self._authenticated:
            return

        try:
            logout_url = f"{self.base_url}/Logout"
            response = self.session.post(logout_url, timeout=10)

            if response.status_code == 204:
                logger.info("Logout successful")
            else:
                logger.warning(f"Logout returned status {response.status_code}")

        except requests.exceptions.RequestException as e:
            logger.warning(f"Logout error (non-critical): {str(e)}")
        finally:
            self._authenticated = False
            self.session.close()

    def get_order(self, doc_entry: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a Sales Order by DocEntry.

        Args:
            doc_entry: The DocEntry of the Sales Order

        Returns:
            Order data as dictionary, or None if not found/error
        """
        if not self._authenticated:
            logger.error("Not authenticated. Call login() first.")
            return None

        url = f"{self.base_url}/Orders({doc_entry})"

        try:
            logger.info(f"Fetching Sales Order DocEntry: {doc_entry}")
            response = self.session.get(url, timeout=30)

            if response.status_code == 200:
                order_data = response.json()
                line_count = len(order_data.get('DocumentLines', []))
                logger.info(f"Retrieved Sales Order {doc_entry} successfully ({line_count} lines)")
                return order_data
            elif response.status_code == 404:
                logger.error(f"Sales Order {doc_entry} not found")
                return None
            else:
                logger.error(f"Failed to retrieve order. Status: {response.status_code}, Response: {response.text}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving order: {str(e)}")
            return None

    def update_order(self, doc_entry: int, update_data: Dict[str, Any]) -> bool:
        """
        Update a Sales Order using PATCH.

        Args:
            doc_entry: The DocEntry of the Sales Order
            update_data: Dictionary containing the fields to update

        Returns:
            True if update successful, False otherwise
        """
        if not self._authenticated:
            logger.error("Not authenticated. Call login() first.")
            return False

        url = f"{self.base_url}/Orders({doc_entry})"

        try:
            logger.info(f"Updating Sales Order DocEntry: {doc_entry}")
            logger.debug(f"PATCH payload: {update_data}")

            response = self.session.patch(url, json=update_data, timeout=30)

            if response.status_code == 204:
                logger.info(f"Sales Order {doc_entry} updated successfully")
                return True
            else:
                logger.error(f"Failed to update order. Status: {response.status_code}, Response: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating order: {str(e)}")
            return False

    def __enter__(self):
        """Context manager entry."""
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.logout()
