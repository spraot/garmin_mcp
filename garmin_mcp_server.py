"""
Simplified MCP Server for Garmin Connect Data
"""

import asyncio
import datetime
import os
from pathlib import Path
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

from garminconnect import Garmin

# Create the Garmin client directly
email = os.environ.get("GARMIN_EMAIL")
password = os.environ.get("GARMIN_PASSWORD")
garmin_client = Garmin(email, password)
print(f"Logging in to Garmin Connect with email: {email}")
garmin_client.login()
print("Login successful!")

# Create FastMCP server
app = FastMCP("Garmin Connect")

@app.tool()
async def list_activities(limit: int = 5) -> str:
    """List recent Garmin activities"""
    try:
        activities = garmin_client.get_activities(0, limit)
        
        if not activities:
            return "No activities found."
        
        result = f"Last {len(activities)} activities:\n\n"
        for idx, activity in enumerate(activities, 1):
            result += f"--- Activity {idx} ---\n"
            result += f"Activity: {activity.get('activityName', 'Unknown')}\n"
            result += f"Type: {activity.get('activityType', {}).get('typeKey', 'Unknown')}\n"
            result += f"Date: {activity.get('startTimeLocal', 'Unknown')}\n"
            result += f"ID: {activity.get('activityId', 'Unknown')}\n\n"
        
        return result
    except Exception as e:
        return f"Error retrieving activities: {str(e)}"

@app.tool()
async def get_activity_details(activity_id: str) -> str:
    """Get detailed information about a specific activity"""
    try:
        activity = garmin_client.get_activity_details(activity_id)
        if not activity:
            return f"No details found for activity {activity_id}"
        
        # Basic formatting of activity details
        result = f"Activity Details for ID {activity_id}:\n\n"
        result += f"Name: {activity.get('activityName', 'Unknown')}\n"
        result += f"Type: {activity.get('activityType', {}).get('typeKey', 'Unknown')}\n"
        result += f"Date: {activity.get('startTimeLocal', 'Unknown')}\n"
        
        return result
    except Exception as e:
        return f"Error retrieving activity details: {str(e)}"

@app.tool()
async def get_heart_rate_data(date: str = None) -> str:
    """Get daily heart rate data"""
    if not date:
        date = datetime.date.today().strftime("%Y-%m-%d")
    
    try:
        hr_data = garmin_client.get_heart_rates(date)
        if not hr_data:
            return f"No heart rate data found for {date}"
        
        result = f"Heart Rate Data for {date}:\n\n"
        result += f"Resting HR: {hr_data.get('restingHeartRate', 0)} bpm\n"
        
        return result
    except Exception as e:
        return f"Error retrieving heart rate data: {str(e)}"

if __name__ == "__main__":
    app.run()
