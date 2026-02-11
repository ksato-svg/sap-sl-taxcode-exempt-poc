"""
Run_Tax_Code_Exempt.PY  v2.0  (Incremental + Batch Mode)

Finds open Sales Order lines with a blank TaxCode and sets them to "EXEMPT".

Performance improvements over v1:
  - Incremental: only orders updated since the last successful run (UpdateDate filter)
  - Batched updates: lines grouped by DocEntry -> one PATCH per order (not per line)
  - $select: limits response fields to reduce payload size
  - Larger page size (500 vs 100) -> fewer round-trips
  - Proper logout in finally block

To force a full re-scan, delete last_run.json in the project root.
"""

import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from logging.handlers import RotatingFileHandler

import keyring
import requests
import urllib3

# ---------------------------------------------------------------------------
# Suppress self-signed certificate warnings
# ---------------------------------------------------------------------------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================
# SETTINGS
# ==============================
BASE_URL = "https://192.168.200.5:50000/b1s/v1"
COMPANY_DB = "TomitaUSA"
TARGET_NODE = ".node3"
LANGUAGE = 25

SERVICE_NAME = "SAP_AutoUpdate"
USER_NAME = "temp"

PAGE_SIZE = 500          # odata.maxpagesize (server may cap lower)
MAX_RETRIES = 3          # retries on transient HTTP errors
RETRY_BACKOFF = 2        # seconds, doubled each retry

# ==============================
# PATH SETTINGS
# ==============================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
LOG_DIR = os.path.join(ROOT_DIR, "1._LOG")
LOG_FILE = os.path.join(LOG_DIR, "update_history.log")
LAST_RUN_FILE = os.path.join(ROOT_DIR, "last_run.json")

os.makedirs(LOG_DIR, exist_ok=True)

# ==============================
# LOGGING
# ==============================
logger = logging.getLogger("TaxCodeExempt")
logger.setLevel(logging.DEBUG)

_file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(
    logging.Formatter("[%(asctime)s] %(levelname)-7s %(message)s",
                      datefmt="%Y-%m-%d %H:%M:%S")
)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setLevel(logging.INFO)
_console_handler.setFormatter(logging.Formatter("%(message)s"))

logger.addHandler(_file_handler)
logger.addHandler(_console_handler)


# ======================================================================
#  LAST-RUN TIMESTAMP  (incremental processing)
# ======================================================================
def load_last_run():
    """Return the last successful run date string (YYYY-MM-DD) or None."""
    if not os.path.exists(LAST_RUN_FILE):
        return None
    try:
        with open(LAST_RUN_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("last_run")
    except (json.JSONDecodeError, IOError, KeyError) as exc:
        logger.warning("Could not read %s: %s", LAST_RUN_FILE, exc)
        return None


def save_last_run(date_str):
    """Persist *date_str* so the next run can skip older orders."""
    try:
        with open(LAST_RUN_FILE, "w", encoding="utf-8") as fh:
            json.dump({
                "last_run": date_str,
                "saved_at": datetime.now().isoformat(),
            }, fh, indent=2)
        logger.debug("Saved last_run = %s", date_str)
    except IOError as exc:
        logger.error("Could not write %s: %s", LAST_RUN_FILE, exc)


# ======================================================================
#  PASSWORD
# ======================================================================
def get_secure_password():
    try:
        password = keyring.get_password(SERVICE_NAME, USER_NAME)
        if password:
            logger.info("[INIT] Password for '%s' retrieved from Vault.", USER_NAME)
            return password
        logger.error("Password for '%s' not found in keyring.", USER_NAME)
        logger.error("Please run '0. Register_Password.bat' first.")
        return None
    except Exception as exc:
        logger.error("Keyring access failed: %s", exc)
        return None


# ======================================================================
#  SESSION / LOGIN / LOGOUT
# ======================================================================
def create_session():
    session = requests.Session()
    session.trust_env = False
    session.verify = False
    session.headers.update({
        "Content-Type": "application/json",
        "User-Agent": "TaxCodeExempt/2.0",
    })
    return session


def login(session, password):
    session.cookies.set("ROUTEID", TARGET_NODE)
    payload = {
        "CompanyDB": COMPANY_DB,
        "UserName": USER_NAME,
        "Password": password,
        "Language": LANGUAGE,
    }
    try:
        logger.info("[LOGIN] Connecting to %s as '%s' ...", TARGET_NODE, USER_NAME)
        resp = session.post(f"{BASE_URL}/Login", json=payload)
        if resp.status_code == 200:
            logger.info("[LOGIN] Success.")
            return True
        logger.error("[LOGIN] Failed (HTTP %s): %s",
                     resp.status_code, resp.text[:300])
        return False
    except requests.RequestException as exc:
        logger.error("[LOGIN] Connection error: %s", exc)
        return False


def logout(session):
    try:
        session.post(f"{BASE_URL}/Logout")
        logger.info("[LOGOUT] Session closed.")
    except Exception:
        pass


# ======================================================================
#  FETCH TARGETS  (incremental, lightweight)
# ======================================================================
def fetch_targets(session, since_date=None):
    """
    Fetch open SO lines that have a blank TaxCode.

    When *since_date* is given (YYYY-MM-DD), only orders whose UpdateDate >= that
    date are retrieved  -> incremental mode.

    Returns:
        list[dict]  on success  (may be empty)
        None        on unrecoverable error
    """
    filters = ["DocumentStatus eq 'bost_Open'"]
    if since_date:
        filters.append(f"UpdateDate ge '{since_date}'")
        logger.info("[FETCH] Incremental mode — orders updated since %s", since_date)
    else:
        # First run: safety floor to avoid ancient data
        filters.append("DocDate gt '2010-01-09'")
        logger.info("[FETCH] Full-scan mode (first run or last_run.json deleted)")

    filter_q = " and ".join(filters)
    next_link = (
        f"{BASE_URL}/Orders"
        f"?$filter={filter_q}"
        f"&$select=DocEntry,DocNum,DocumentLines"
    )

    session.headers["Prefer"] = f"odata.maxpagesize={PAGE_SIZE}"

    targets = []
    order_count = 0
    page = 0

    try:
        while next_link:
            page += 1
            logger.debug("  page %d ...", page)

            resp = _get_with_retry(session, next_link)
            if resp is None or resp.status_code != 200:
                status = resp.status_code if resp else "no response"
                logger.error("[FETCH] Failed on page %d (HTTP %s)", page, status)
                return None

            data = resp.json()
            orders = data.get("value", [])
            order_count += len(orders)

            for order in orders:
                doc_entry = order["DocEntry"]
                doc_num = order["DocNum"]
                for line in order.get("DocumentLines", []):
                    if (line.get("LineStatus") == "bost_Open"
                            and not line.get("TaxCode")):
                        targets.append({
                            "DocEntry": doc_entry,
                            "DocNum": doc_num,
                            "LineNum": line["LineNum"],
                        })

            raw_next = data.get("odata.nextLink")
            if raw_next:
                next_link = (raw_next if raw_next.startswith("http")
                             else f"{BASE_URL}/{raw_next}")
            else:
                next_link = None

    except requests.RequestException as exc:
        logger.error("[FETCH] Network error: %s", exc)
        return None

    logger.info(
        "[FETCH] Scanned %d order(s) in %d page(s) — %d blank-tax-code line(s) found.",
        order_count, page, len(targets),
    )
    return targets


# ======================================================================
#  BATCH UPDATE  (grouped by DocEntry)
# ======================================================================
def update_targets(session, targets):
    """
    PATCH orders, sending one request per DocEntry (all lines bundled).

    Returns (success_lines, failed_lines).
    """
    grouped = defaultdict(list)
    docnum_map = {}
    for t in targets:
        grouped[t["DocEntry"]].append(t["LineNum"])
        docnum_map[t["DocEntry"]] = t["DocNum"]

    logger.info(
        "[UPDATE] %d line(s) across %d order(s) to patch.",
        len(targets), len(grouped),
    )

    ok = 0
    fail = 0

    for doc_entry, line_nums in grouped.items():
        doc_num = docnum_map[doc_entry]
        url = f"{BASE_URL}/Orders({doc_entry})"
        body = {
            "DocumentLines": [
                {"LineNum": ln, "TaxCode": "EXEMPT"} for ln in line_nums
            ]
        }

        try:
            resp = _patch_with_retry(session, url, body)
            if resp is not None and resp.status_code == 204:
                ok += len(line_nums)
                lines_str = ", ".join(str(ln) for ln in line_nums)
                logger.info("  [OK]   SO#%s  line(s) [%s] -> EXEMPT", doc_num, lines_str)
            else:
                fail += len(line_nums)
                status = resp.status_code if resp else "no response"
                detail = resp.text[:300] if resp else ""
                logger.warning("  [FAIL] SO#%s  HTTP %s  %s", doc_num, status, detail)
        except requests.RequestException as exc:
            fail += len(line_nums)
            logger.error("  [ERROR] SO#%s  %s", doc_num, exc)

    return ok, fail


# ======================================================================
#  HTTP HELPERS  (retry on transient errors)
# ======================================================================
def _get_with_retry(session, url):
    return _request_with_retry(session, "GET", url)


def _patch_with_retry(session, url, json_body):
    return _request_with_retry(session, "PATCH", url, json_body=json_body)


def _request_with_retry(session, method, url, json_body=None):
    """
    Execute an HTTP request with exponential-backoff retry on transient errors
    (connection errors, 502/503/504).
    """
    wait = RETRY_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if method == "GET":
                resp = session.get(url)
            elif method == "PATCH":
                resp = session.patch(url, json=json_body)
            else:
                raise ValueError(f"Unsupported method: {method}")

            if resp.status_code not in (502, 503, 504):
                return resp

            logger.warning(
                "  Transient HTTP %s on attempt %d/%d — retrying in %ds ...",
                resp.status_code, attempt, MAX_RETRIES, wait,
            )
        except requests.ConnectionError as exc:
            logger.warning(
                "  Connection error on attempt %d/%d: %s — retrying in %ds ...",
                attempt, MAX_RETRIES, exc, wait,
            )

        if attempt < MAX_RETRIES:
            time.sleep(wait)
            wait *= 2

    logger.error("  All %d attempts failed for %s %s", MAX_RETRIES, method, url)
    return None


# ======================================================================
#  MAIN
# ======================================================================
def main():
    run_start = datetime.now()
    run_date = run_start.strftime("%Y-%m-%d")

    logger.info("")
    logger.info("=" * 58)
    logger.info("  SAP TAX-CODE EXEMPT UPDATER  v2.0  (Incremental + Batch)")
    logger.info("  Started: %s", run_start.strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 58)

    # 1) Password -------------------------------------------------------
    password = get_secure_password()
    if not password:
        return

    # 2) Login ----------------------------------------------------------
    session = create_session()
    if not login(session, password):
        return

    try:
        # 3) Determine incremental window --------------------------------
        last_run = load_last_run()

        # 4) Fetch candidates --------------------------------------------
        targets = fetch_targets(session, since_date=last_run)
        if targets is None:
            logger.error("[ABORT] Fetch failed — will retry on next run.")
            return

        if not targets:
            logger.info("[DONE] No blank-tax-code lines found. Everything is clean.")
            save_last_run(run_date)
            return

        # 5) Batch-update -------------------------------------------------
        ok, fail = update_targets(session, targets)

        # 6) Checkpoint ---------------------------------------------------
        if fail == 0:
            save_last_run(run_date)
        else:
            logger.warning(
                "[WARN] %d line(s) failed — last_run NOT advanced so they "
                "will be retried on the next run.", fail,
            )

        elapsed = (datetime.now() - run_start).total_seconds()
        logger.info("-" * 58)
        logger.info("  RESULT: %d updated, %d failed  (%.1fs)", ok, fail, elapsed)
        logger.info("-" * 58)

    finally:
        logout(session)


if __name__ == "__main__":
    main()
