# Collective Auto Investment

A web application that helps users understand the power of systematic investment in the S&P 500 index.

## Features

- Interactive S&P 500 performance visualization
- Systematic Investment Plan (SIP) calculator
- NYU-themed design
- Real-time data from Alpaca API

## Prerequisites

- Python 3.8+
- Alpaca API credentials

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/collective-auto-investment.git
cd collective-auto-investment
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory with your Alpaca API credentials:
```
ALPACA_API_KEY=your_api_key
ALPACA_API_SECRET=your_api_secret
```

5. Run the application:
```bash
uvicorn app:app --reload
```

The application will be available at `http://localhost:8000`

## Deployment on Render

1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Set the following:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Add your environment variables in Render's dashboard:
   - `ALPACA_API_KEY`
   - `ALPACA_API_SECRET`

## Project Structure

```
collective-auto-investment/
├── app.py              # Main application file
├── config.py           # Configuration and credentials
├── requirements.txt    # Python dependencies
├── static/            # Static files (CSS, JS, images)
├── templates/         # HTML templates
└── README.md          # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 