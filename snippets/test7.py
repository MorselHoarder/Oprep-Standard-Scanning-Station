import logging

log_format = "%(asctime)s - %(levelname)s - %(message)s"
logging.basicConfig(
    format=log_format, handlers=[logging.FileHandler("errors.log")], level=logging.INFO
)
logger = logging.getLogger("universal")

CONNECTION_ERRORS = (OSError, ConnectionError, TimeoutError, ZeroDivisionError)

try:
    1 / 0
except CONNECTION_ERRORS as e:
    logger.warning(
        f"Connection Error Raised: {type(e)}: {e}. %s",
        f"Attempting API restart in {120/60} minutes.",
    )
