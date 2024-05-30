import os
from dotenv import load_dotenv
from chalicelib.utils import logger

# Load .env file from the specified path
env_path = os.path.join(os.path.dirname(__file__), '../.env')
logger.info(f"Loading environment variables from {env_path}")
load_dotenv(dotenv_path=env_path)

class Config:
    def __init__(self):
        # Load from environment variables
        self.service_url = os.getenv('SERVICE_URL', 'https://cdnapi-ev.kaltura.com/')
        
        logger.info(f"Service URL: {self.service_url}")

config = Config()
