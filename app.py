from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime, timedelta
import requests
import json
import time
import sqlite3
import os
import shutil
from typing import List
from config import (
    ALPACA_API_KEY,
    ALPACA_API_SECRET,
    ALPACA_BASE_URL,
    APP_NAME,
    APP_DESCRIPTION,
    APP_EMAIL
)

app = FastAPI(title=APP_NAME, description=APP_DESCRIPTION)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# WebSocket connections
active_connections: List[WebSocket] = []

# Database setup
def init_db():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS interest_data
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         ip_address TEXT,
         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS email_subscribers
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         email TEXT UNIQUE,
         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
    ''')
    conn.commit()
    conn.close()

def backup_db():
    """Create a backup of the database with timestamp"""
    try:
        # Create backups directory if it doesn't exist
        if not os.path.exists('backups'):
            os.makedirs('backups')
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'backups/app_backup_{timestamp}.db'
        
        # Copy the database file
        shutil.copy2('app.db', backup_file)
        print(f"Database backup created: {backup_file}")
        
        # Keep only the last 5 backups
        backups = sorted([f for f in os.listdir('backups') if f.startswith('app_backup_')])
        if len(backups) > 5:
            for old_backup in backups[:-5]:
                os.remove(os.path.join('backups', old_backup))
                print(f"Removed old backup: {old_backup}")
    except Exception as e:
        print(f"Error creating backup: {str(e)}")

# Initialize database
init_db()

# Create initial backup
backup_db()

# Security
ADMIN_PASSWORD = "isha"

async def verify_admin_password(password: str):
    if password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=401,
            detail="Invalid password"
        )
    return True

@app.get("/export-data")
async def export_data(password: str, verified: bool = Depends(verify_admin_password)):
    try:
        conn = sqlite3.connect('app.db')
        c = conn.cursor()
        
        # Get all interest data
        c.execute('''
            SELECT ip_address, timestamp 
            FROM interest_data 
            ORDER BY timestamp DESC
        ''')
        interest_data = c.fetchall()
        
        # Get all email subscribers
        c.execute('''
            SELECT email, timestamp 
            FROM email_subscribers 
            ORDER BY timestamp DESC
        ''')
        email_data = c.fetchall()
        
        # Get summary statistics
        c.execute('SELECT COUNT(*) FROM interest_data')
        total_interest = c.fetchone()[0]
        
        c.execute('SELECT COUNT(DISTINCT ip_address) FROM interest_data')
        unique_visitors = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM email_subscribers')
        total_subscribers = c.fetchone()[0]
        
        conn.close()
        
        return {
            "summary": {
                "total_interest": total_interest,
                "unique_visitors": unique_visitors,
                "total_subscribers": total_subscribers
            },
            "interest_data": [
                {
                    "ip_address": row[0],
                    "timestamp": row[1]
                } for row in interest_data
            ],
            "email_data": [
                {
                    "email": row[0],
                    "timestamp": row[1]
                } for row in email_data
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error exporting data: {str(e)}"
        )

@app.get("/sp500-data")
async def get_sp500_data():
    try:
        print("\n=== Starting S&P 500 Data Fetch ===")
        # Calculate date range (using historical data)
        end_date = datetime.now() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=365)  # One year ago
        
        print(f"Date Range:")
        print(f"Start: {start_date}")
        print(f"End: {end_date}")
        
        # Format dates for Alpaca API (ISO 8601 format)
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # Alpaca API endpoint for historical data
        url = f"{ALPACA_BASE_URL}/stocks/bars?symbols=SPY&start={start_str}&end={end_str}&timeframe=1Day&limit=1000"
        headers = {
            'APCA-API-KEY-ID': ALPACA_API_KEY,
            'APCA-API-SECRET-KEY': ALPACA_API_SECRET
        }
        
        print("\nAPI Request Details:")
        print(f"URL: {url}")
        print(f"Headers: {json.dumps(headers, indent=2)}")
        
        # Add retry logic
        max_retries = 3
        data = None
        for attempt in range(max_retries):
            try:
                print(f"\nAttempt {attempt + 1} of {max_retries}")
                print("Making request to Alpaca API...")
                
                response = requests.get(url, headers=headers)
                print(f"Response Status Code: {response.status_code}")
                print(f"Response Headers: {json.dumps(dict(response.headers), indent=2)}")
                print(f"Response Content: {response.text[:500]}")  # Print first 500 chars of response
                
                if response.status_code == 200:
                    data = response.json()
                    print("\nSuccessfully received data:")
                    print(f"Data keys: {list(data.keys())}")
                    if data.get('bars') and data['bars'].get('SPY'):
                        print("Found SPY data in response")
                        break
                    else:
                        print("No SPY data found in response")
                elif response.status_code == 401:
                    print("\nAuthentication failed. Please check API credentials.")
                    print("Response content:", response.text)
                    break
                elif response.status_code == 403:
                    print("\nAccess forbidden. Please check API permissions.")
                    print("Response content:", response.text)
                    break
                elif response.status_code == 404:
                    print("\nEndpoint not found. Please check API URL.")
                    print("Response content:", response.text)
                    break
                else:
                    print(f"\nUnexpected status code: {response.status_code}")
                    print("Response content:", response.text)
                
                print(f"\nAttempt {attempt + 1} failed, retrying...")
                time.sleep(1)
            except Exception as e:
                print(f"\nException during attempt {attempt + 1}:")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)
        
        if not data or not data.get('bars') or not data['bars'].get('SPY'):
            print("\nNo valid data available for SPY")
            return {
                "dates": [],
                "prices": []
            }
            
        # Format data for Chart.js
        bars = data['bars']['SPY']
        print(f"\nProcessing {len(bars)} data points")
        dates = [bar['t'] for bar in bars]
        prices = [bar['c'] for bar in bars]
        
        print(f"Formatted {len(dates)} dates and {len(prices)} prices")
        print("First few data points:")
        for i in range(min(3, len(dates))):
            print(f"Date: {dates[i]}, Price: {prices[i]}")
        
        print("\n=== S&P 500 Data Fetch Complete ===\n")
        return {
            "dates": dates,
            "prices": prices
        }
    except Exception as e:
        print(f"\nError in get_sp500_data:")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        return {
            "dates": [],
            "prices": []
        }

@app.websocket("/ws/interest")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        # Send initial count
        conn = sqlite3.connect('app.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM interest_data')
        count = c.fetchone()[0]
        conn.close()
        await websocket.send_json({"count": count})
        
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        active_connections.remove(websocket)

async def broadcast_interest_count():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM interest_data')
    count = c.fetchone()[0]
    conn.close()
    
    for connection in active_connections:
        try:
            await connection.send_json({"count": count})
        except Exception as e:
            print(f"Error broadcasting to WebSocket: {str(e)}")

@app.post("/increment-interest")
async def increment_interest(request: Request):
    client_ip = request.client.host
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute('INSERT INTO interest_data (ip_address) VALUES (?)', (client_ip,))
    conn.commit()
    
    # Get the updated count
    c.execute('SELECT COUNT(*) FROM interest_data')
    count = c.fetchone()[0]
    conn.close()
    
    # Backup after each interest increment
    backup_db()
    
    # Broadcast new count to all connected clients
    await broadcast_interest_count()
    
    return {"count": count}

@app.post("/subscribe")
async def subscribe_email(request: Request):
    try:
        data = await request.json()
        email = data.get('email')
        if not email:
            raise HTTPException(status_code=400, detail="Email is required")
            
        conn = sqlite3.connect('app.db')
        c = conn.cursor()
        c.execute('INSERT INTO email_subscribers (email) VALUES (?)', (email,))
        conn.commit()
        conn.close()
        
        # Backup after each subscription
        backup_db()
        
        return {"message": "Successfully subscribed!"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email already subscribed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/stats")
async def get_admin_stats(request: Request):
    try:
        # Get the authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization header"
            )
        
        # Extract the token
        token = auth_header.split(' ')[1]
        
        # Verify the token
        if token != ADMIN_PASSWORD:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )
        
        # Get database connection
        conn = sqlite3.connect('app.db')
        c = conn.cursor()
        
        # Get summary statistics
        c.execute('SELECT COUNT(*) FROM interest_data')
        total_interest = c.fetchone()[0]
        
        c.execute('SELECT COUNT(DISTINCT ip_address) FROM interest_data')
        unique_visitors = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM email_subscribers')
        total_subscribers = c.fetchone()[0]
        
        # Get recent interest data
        c.execute('''
            SELECT ip_address, timestamp 
            FROM interest_data 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''')
        recent_interest = c.fetchall()
        
        # Get recent subscribers
        c.execute('''
            SELECT email, timestamp 
            FROM email_subscribers 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''')
        recent_subscribers = c.fetchall()
        
        conn.close()
        
        return {
            "total_interest": total_interest,
            "unique_visitors": unique_visitors,
            "total_subscribers": total_subscribers,
            "recent_interest": recent_interest,
            "recent_subscribers": recent_subscribers
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching admin stats: {str(e)}"
        )

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    try:
        # Get the authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return templates.TemplateResponse(
                "landing_page.html",
                {"request": request}
            )
        
        # Extract the token
        token = auth_header.split(' ')[1]
        
        # Verify the token
        if token != ADMIN_PASSWORD:
            return templates.TemplateResponse(
                "landing_page.html",
                {"request": request}
            )
        
        # If token is valid, show admin page
        return templates.TemplateResponse(
            "admin_page.html",
            {"request": request}
        )
    except Exception as e:
        print(f"Error in admin page: {str(e)}")
        return templates.TemplateResponse(
            "landing_page.html",
            {"request": request}
        )

@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    try:
        conn = sqlite3.connect('app.db')
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM interest_data')
        interest_count = c.fetchone()[0]
        conn.close()
        
        return templates.TemplateResponse(
            "landing_page.html",
            {
                "request": request,
                "interest_count": interest_count,
                "app_name": APP_NAME,
                "app_description": APP_DESCRIPTION,
                "app_email": APP_EMAIL
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "landing_page.html",
            {
                "request": request,
                "interest_count": 0,
                "app_name": APP_NAME,
                "app_description": APP_DESCRIPTION,
                "app_email": APP_EMAIL
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 