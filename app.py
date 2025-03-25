from fastapi import FastAPI, Request, HTTPException, Depends, WebSocket, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import requests
import json
import time
import sqlite3
import os
import shutil
from typing import List, Any
from config import (
    ALPACA_API_KEY,
    ALPACA_API_SECRET,
    ALPACA_BASE_URL,
    APP_NAME,
    APP_DESCRIPTION,
    APP_EMAIL
)
from dotenv import load_dotenv
import pandas as pd
import io
import asyncio
import aiohttp
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get admin password from environment
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

if not ADMIN_PASSWORD:
    raise ValueError("Missing required environment variable: ADMIN_PASSWORD")

app = FastAPI(title=APP_NAME, description=APP_DESCRIPTION)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "upgrade-insecure-requests"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# Mount static files with custom response class
class SecureStaticFiles(StaticFiles):
    async def file_response(self, scope, receive, send, file_path, stat_result):
        response = await super().file_response(scope, receive, send, file_path, stat_result)
        response.headers["Cache-Control"] = "public, max-age=31536000"
        return response

# Override url_for to always return HTTPS URLs for static files
def url_for(request: Request, name: str, **path_params: Any) -> str:
    url = request.url_for(name, **path_params)
    if name.startswith("static"):
        return url.replace("http://", "https://")
    return url

# Mount static files with custom response class
app.mount("/static", SecureStaticFiles(directory="static"), name="static")

# Templates with secure URLs
templates = Jinja2Templates(directory="templates")

# Override url_for to always use HTTPS
def url_for(name: str, path: str, _scheme: str = "https") -> str:
    return f"https://the-vault-production.up.railway.app{path}"

templates.env.globals["url_for"] = url_for

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
        # Get the password from query parameters
        password = request.query_params.get('password')
        print(f"Received password: {password}")  # Debug print
        
        # If no password provided or password is incorrect, return unauthorized
        if not password or password != ADMIN_PASSWORD:
            print("Password verification failed")  # Debug print
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        print("Password verified successfully")  # Debug print
        
        # Get stats from database
        with sqlite3.connect('app.db') as conn:
            cursor = conn.cursor()
            
            # Get total interest (count of interest entries)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM interest_data
            """)
            total_interest = cursor.fetchone()[0]
            
            # Get total subscribers
            cursor.execute("""
                SELECT COUNT(*) 
                FROM email_subscribers
            """)
            total_subscribers = cursor.fetchone()[0]
            
            # Get recent interest (last 5)
            cursor.execute("""
                SELECT ip_address, timestamp 
                FROM interest_data 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            recent_interest = [
                {"amount": 1, "timestamp": timestamp}  # Each interest entry counts as 1
                for ip_address, timestamp in cursor.fetchall()
            ]
            
            # Get recent subscribers (last 5)
            cursor.execute("""
                SELECT email, timestamp 
                FROM email_subscribers 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            recent_subscribers = [
                {"email": email, "timestamp": timestamp}
                for email, timestamp in cursor.fetchall()
            ]
            
            return {
                "total_interest": total_interest,
                "total_subscribers": total_subscribers,
                "recent_interest": recent_interest,
                "recent_subscribers": recent_subscribers
            }
    except Exception as e:
        print(f"Error in admin stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/download-csv")
async def download_csv(request: Request):
    try:
        # Get the password from query parameters
        password = request.query_params.get('password')
        print(f"\n=== Download CSV Request Debug ===")
        print(f"Received password: {password}")
        print(f"Expected password: {ADMIN_PASSWORD}")
        
        # If no password provided or password is incorrect, return unauthorized
        if not password or password != ADMIN_PASSWORD:
            print("Password verification failed")
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        print("Password verified successfully")
        
        # Get data from database
        with sqlite3.connect('app.db') as conn:
            cursor = conn.cursor()
            
            # Get interest data
            cursor.execute("""
                SELECT ip_address, timestamp 
                FROM interest_data 
                ORDER BY timestamp DESC
            """)
            interest_data = cursor.fetchall()
            
            # Get subscriber data
            cursor.execute("""
                SELECT email, timestamp 
                FROM email_subscribers 
                ORDER BY timestamp DESC
            """)
            subscriber_data = cursor.fetchall()
            
            # Create CSV content
            csv_content = []
            
            # Add interest data
            csv_content.append("Interest Data")
            csv_content.append("IP Address,Timestamp")
            for ip, timestamp in interest_data:
                csv_content.append(f"{ip},{timestamp}")
            
            # Add subscriber data
            csv_content.append("\nSubscriber Data")
            csv_content.append("Email,Timestamp")
            for email, timestamp in subscriber_data:
                csv_content.append(f"{email},{timestamp}")
            
            # Join all lines
            csv_text = "\n".join(csv_content)
            
            # Create response with CSV content
            return Response(
                content=csv_text,
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="admin_stats_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
                }
            )
    except Exception as e:
        print(f"Error in download CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin")
async def admin_page(request: Request):
    try:
        # Get the password from query parameters
        password = request.query_params.get('password')
        print(f"\n=== Admin Page Request Debug ===")
        print(f"Received password: {password}")
        print(f"Expected password: {ADMIN_PASSWORD}")
        
        # If no password provided or password is incorrect, return login page
        if not password or password != ADMIN_PASSWORD:
            print("Password verification failed")
            return templates.TemplateResponse(
                "admin_login.html",
                {"request": request}
            )
        
        print("Password verified successfully")
        # If password is correct, show admin page
        return templates.TemplateResponse(
            "admin_page.html",
            {"request": request}
        )
    except Exception as e:
        print(f"Error in admin page: {str(e)}")
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request}
        )

@app.post("/admin")
async def admin_login(request: Request):
    try:
        # Check if password was submitted
        form_data = await request.form()
        password = form_data.get("password", "")
        print(f"Received password: {password}")  # Debug print
        
        if password == ADMIN_PASSWORD:
            print("Password verified successfully")  # Debug print
            # Password is correct, show admin page
            return templates.TemplateResponse("admin_page.html", {"request": request})
        else:
            print("Password verification failed")  # Debug print
            # Show login form with error if incorrect password
            return templates.TemplateResponse("admin_login.html", {"request": request, "error": "Incorrect password"})
            
    except Exception as e:
        print(f"Error in admin_login: {str(e)}")
        return templates.TemplateResponse("admin_login.html", {"request": request, "error": "An error occurred"})

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