import logging

log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=log_format, 
                    handlers=[logging.FileHandler('errors.log')],
                    level=logging.INFO)
logger = logging.getLogger("universal")

