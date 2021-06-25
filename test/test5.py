import logging


log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=log_format, handlers=[logging.FileHandler('errors.log')])
logger = logging.getLogger(__name__)

try:
    1/0
except:
    logger.warning(f'Unexpected Error {1/2} %s', 'another line', exc_info=1)

