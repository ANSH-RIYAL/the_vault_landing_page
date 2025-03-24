import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Alpaca API Configuration
ALPACA_API_KEY = os.getenv('ALPACA_API_KEY')
ALPACA_API_SECRET = os.getenv('ALPACA_API_SECRET')
ALPACA_BASE_URL = os.getenv('ALPACA_BASE_URL')

# Application Configuration
APP_NAME = os.getenv('APP_NAME', 'Collective Auto Investment')
APP_DESCRIPTION = os.getenv('APP_DESCRIPTION', 'A web application that helps users understand the power of systematic investment in the S&P 500 index.')
APP_EMAIL = os.getenv('APP_EMAIL', 'ask.the.vault.1a@gmail.com')

# Validate required environment variables
if not all([ALPACA_API_KEY, ALPACA_API_SECRET, ALPACA_BASE_URL]):
    raise ValueError("Missing required environment variables. Please check your .env file.") 