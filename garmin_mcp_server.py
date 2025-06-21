"""
Modular MCP Server for Garmin Connect Data
"""

import asyncio
import time
import os
import datetime
import requests
import threading
from pathlib import Path
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

from garth.exc import GarthHTTPError
from garminconnect import Garmin, GarminConnectAuthenticationError

# Import all modules
from modules import activity_management
from modules import health_wellness
from modules import user_profile
from modules import devices
from modules import gear_management
from modules import weight_management
from modules import challenges
from modules import training
from modules import workouts
from modules import data_management
from modules import womens_health

# Get credentials from environment
email = os.environ.get("GARMIN_EMAIL")
password = os.environ.get("GARMIN_PASSWORD")
tokenstore = os.getenv("GARMINTOKENS") or "~/.garminconnect"
tokenstore_base64 = os.getenv("GARMINTOKENS_BASE64") or "~/.garminconnect_base64"

LOGIN_STATE_SUCCESS = 0
LOGIN_STATE_MFA = 1
LOGIN_STATE_ERROR = 2
login_state = None
need_mfa = None
mfa_code = None
lock = threading.Lock()

def init_api(email, password):
    """Initialize Garmin API with your credentials."""

    try:
        # Using Oauth1 and OAuth2 token files from directory
        print(
            f"Trying to login to Garmin Connect using token data from directory '{tokenstore}'...\n"
        )

        # Using Oauth1 and Oauth2 tokens from base64 encoded string
        # print(
        #     f"Trying to login to Garmin Connect using token data from file '{tokenstore_base64}'...\n"
        # )
        # dir_path = os.path.expanduser(tokenstore_base64)
        # with open(dir_path, "r") as token_file:
        #     tokenstore = token_file.read()

        garmin = Garmin()
        garmin.login(tokenstore)

    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        # Session is expired. You'll need to log in again
        print(
            "Login tokens not present, login with your Garmin Connect credentials to generate them.\n"
            f"They will be stored in '{tokenstore}' for future use.\n"
        )

        garmin = Garmin(
            email=email, password=password, is_cn=False, prompt_mfa=get_mfa
        )

        def login():
            global login_state
            try:
                print("Logging in...")
                garmin.login()
            
                # Save Oauth1 and Oauth2 token files to directory for next login
                garmin.garth.dump(tokenstore)
                print(
                    f"Oauth tokens stored in '{tokenstore}' directory for future use. (first method)\n"
                )
                # Encode Oauth1 and Oauth2 tokens to base64 string and safe to file for next login (alternative way)
                token_base64 = garmin.garth.dumps()
                dir_path = os.path.expanduser(tokenstore_base64)
                with open(dir_path, "w") as token_file:
                    token_file.write(token_base64)
                print(
                    f"Oauth tokens encoded as base64 string and saved to '{dir_path}' file for future use. (second method)\n"
                )
                
                with lock:
                    login_state = LOGIN_STATE_SUCCESS
            except (
                FileNotFoundError,
                GarthHTTPError,
                GarminConnectAuthenticationError,
                requests.exceptions.HTTPError,
            ) as err:
                print(err)
                with lock:
                    login_state = LOGIN_STATE_ERROR

        thread = threading.Thread(target=login)
        thread.start()

        print('waiting for login or mfa')
        while True:
            time.sleep(0.1)
            with lock:
                if need_mfa:
                    return LOGIN_STATE_MFA, garmin
                if login_state is not None:
                    if login_state != LOGIN_STATE_SUCCESS:
                        return LOGIN_STATE_ERROR, None
                    else:
                        break

    return LOGIN_STATE_SUCCESS, garmin

def get_mfa() -> str:
    """
    Called synchronously by garminconnect.  We block until the user
    submits the code via the MCP tool below.
    """
    global need_mfa, mfa_code
    print("MFA required")
    with lock:
        need_mfa = True
    
    # Since we're in a thread, we need to wait synchronously
    timeout = 1800
    start_time = time.time()
    while True:
        time.sleep(0.1)
        with lock:
            if mfa_code:
                code = mfa_code
                mfa_code = None
                need_mfa = False
                return code
        if time.time() - start_time > timeout:
            raise TimeoutError("MFA timeout")

def main():
    """Initialize the MCP server and register all tools"""
    
    # Initialize Garmin client
    ls, garmin_client = init_api(email, password)
    if ls == LOGIN_STATE_ERROR:
        print("Failed to initialize Garmin Connect client. Exiting.")
        return
    
    if ls == LOGIN_STATE_MFA:
        print("Garmin Connect client initialized, but MFA is required, need user to enter code before using any tools")
    
    if ls == LOGIN_STATE_SUCCESS:
        print("Garmin Connect client initialized successfully.")
    
    # Configure all modules with the Garmin client
    activity_management.configure(garmin_client)
    health_wellness.configure(garmin_client)
    user_profile.configure(garmin_client)
    devices.configure(garmin_client)
    gear_management.configure(garmin_client)
    weight_management.configure(garmin_client)
    challenges.configure(garmin_client)
    training.configure(garmin_client)
    workouts.configure(garmin_client)
    data_management.configure(garmin_client)
    womens_health.configure(garmin_client)
    
    # Create the MCP app
    app = FastMCP("Garmin Connect v1.0")
    
    # Register tools from all modules
    app = activity_management.register_tools(app)
    app = health_wellness.register_tools(app)
    app = user_profile.register_tools(app)
    app = devices.register_tools(app)
    app = gear_management.register_tools(app)
    app = weight_management.register_tools(app)
    app = challenges.register_tools(app)
    app = training.register_tools(app)
    app = workouts.register_tools(app)
    app = data_management.register_tools(app)
    app = womens_health.register_tools(app)
    
    # Add activity listing tool directly to the app
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
                result += (
                    f"Type: {activity.get('activityType', {}).get('typeKey', 'Unknown')}\n"
                )
                result += f"Date: {activity.get('startTimeLocal', 'Unknown')}\n"
                result += f"ID: {activity.get('activityId', 'Unknown')}\n\n"

            return result
        except Exception as e:
            return f"Error retrieving activities: {str(e)}"

    if ls == LOGIN_STATE_MFA:
        # Add tool for entering MFA code
        @app.tool()
        async def enter_mfa_code(code: int) -> str:
            global mfa_code, login_state
            """
            Enter MFA code from user to complete login
            VERY IMPORTANT: THIS MUST BE DONE ONCE BEFORE USING ANY OTHER TOOLS
            If any tool fails due to OAuth error, you must ask the user to enter the MFA code and run this tool
            before using any other tools.
            
            Args:
                code (int): MFA code from user (VERY IMPORTANT, you must ask the user to enter this code)
            """
            with lock:
                mfa_code = code
            start_time = time.time()
            while True:
                time.sleep(0.1)
                with lock:
                    if login_state is not None:
                        break
                if time.time() - start_time > 30:
                    return "Timed out waiting for login to complete"
            if login_state == LOGIN_STATE_ERROR:
                return "Failed to complete login"
            return "MFA code entered successfully."
    
    # Run the MCP server
    app.run()


if __name__ == "__main__":
    main()
