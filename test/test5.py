import logging


log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(format=log_format, handlers=[logging.FileHandler('errors.log')])
logger = logging.getLogger(__name__)

try:
    1/0
except:
    logger.warning('Unexpected Error %s', 'another line', exc_info=1)

