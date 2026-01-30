# FILE: app.py
# This is the main file for your Flask web application.

import os
import requests
import psycopg2
from psycopg2.extras import Json
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# --- Configuration ---
# It's best practice to load sensitive data from environment variables.
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL") # Example: "postgresql://user:password@host:port/dbname"

# --- Flask App Initialization ---
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "a_default_secret_key_for_development")

# --- Database Functions ---

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        # This error is common if the database isn't running or credentials are wrong.
        print(f"Error connecting to the database: {e}")
        return None

def init_db():
    """Initializes the database by creating the necessary table if it doesn't exist."""
    conn = get_db_connection()
    if conn is None:
        print("Could not initialize database. Connection failed.")
        return
        
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                id SERIAL PRIMARY KEY,
                user_name VARCHAR(100) NOT NULL,
                city VARCHAR(100) NOT NULL,
                forecast_data JSONB NOT NULL,
                saved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
    conn.commit()
    conn.close()
    print("Database initialized successfully.")

def save_forecast_to_db(user_name, city, forecast_data):
    """Saves a user's forecast data to the database."""
    conn = get_db_connection()
    if conn is None:
        return False, "Database connection failed."

    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO forecasts (user_name, city, forecast_data) VALUES (%s, %s, %s)",
                (user_name, city, Json(forecast_data))
            )
        conn.commit()
        return True, "Forecast saved successfully!"
    except Exception as e:
        conn.rollback()
        print(f"Database error: {e}")
        return False, "Failed to save forecast due to a database error."
    finally:
        conn.close()

# --- OpenWeatherMap API Function ---

def get_weather_forecast(city):
    """Fetches 5-day weather forecast data from the OpenWeatherMap API."""
    if not OPENWEATHER_API_KEY:
        return None, "OpenWeatherMap API key is not configured."

    # API endpoint for 5-day/3-hour forecast
    api_url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raises an exception for bad status codes (4xx or 5xx)
        data = response.json()

        # Process the data to make it easier to display in the template
        processed_forecasts = []
        # We only want one forecast per day, so we'll grab the forecast for midday (12:00)
        for forecast in data.get('list', []):
            if "12:00:00" in forecast['dt_txt']:
                processed_forecasts.append({
                    'date': datetime.fromtimestamp(forecast['dt']).strftime('%A, %b %d'),
                    'temp': round(forecast['main']['temp']),
                    'description': forecast['weather'][0]['description'].title(),
                    'icon': forecast['weather'][0]['icon']
                })
        
        # We also need the raw data for saving to the database
        city_info = {
            'name': data['city']['name'],
            'country': data['city']['country']
        }
        
        return processed_forecasts, city_info, data, None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None, None, None, f"Could not find weather data for '{city}'. Please check the spelling."
        else:
            return None, None, None, f"An API error occurred: {e}"
    except requests.exceptions.RequestException as e:
        return None, None, None, f"A network error occurred: {e}"


# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    """Handles the main page, form submission, and displaying the forecast."""
    if request.method == 'POST':
        user_name = request.form.get('name')
        city = request.form.get('city')

        if not user_name or not city:
            flash("Please enter both your name and a city.", "error")
            return redirect(url_for('index'))

        # Fetch weather data
        forecasts, city_info, raw_data, error = get_weather_forecast(city)

        if error:
            flash(error, "error")
            return redirect(url_for('index'))

        return render_template(
            'index.html', 
            forecasts=forecasts, 
            city_info=city_info, 
            user_name=user_name,
            raw_data_for_db=raw_data # Pass raw data for the save form
        )

    # For a GET request, just show the page
    return render_template('index.html')

@app.route('/save_forecast', methods=['POST'])
def save_forecast():
    """Handles the form submission for saving the forecast to the database."""
    user_name = request.form.get('user_name')
    city = request.form.get('city')
    # The raw JSON data is passed as a string, so we need to convert it back to a dict
    import json
    raw_data_str = request.form.get('raw_data')

    if not user_name or not city or not raw_data_str:
        flash("Missing data to save the forecast.", "error")
        return redirect(url_for('index'))

    try:
        raw_data = json.loads(raw_data_str)
        success, message = save_forecast_to_db(user_name, city, raw_data)
        flash(message, "success" if success else "error")
    except json.JSONDecodeError:
        flash("Invalid forecast data format.", "error")

    return redirect(url_for('index'))

# --- Main Execution ---

if __name__ == '__main__':
    # This block runs only when you execute the script directly (e.g., `python app.py`)
    # It will initialize the database and then start the Flask development server.
    init_db()
    #app.run(debug=True) # debug=True provides helpful error messages during development
    app.run(host='0.0.0.0', port=5000)
