from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc
from flask_migrate import Migrate
from datetime import datetime, timezone, date, timedelta
import calendar 
import json
import os


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///locations.db'
app.config['TEMPLATES_AUTO_RELOAD'] = True

#initiate database
db=SQLAlchemy(app)
migrate = Migrate(app, db)

#API endpoint and key
API_KEY = 'c24adc3699d398ec4a13585f3590d00e'
API_URL = 'http://api.openweathermap.org/data/2.5/weather'
API7_URL = 'https://api.openweathermap.org/data/3.0/onecall'
GEO_URL = "http://api.openweathermap.org/geo/1.0/direct"

#create models for db
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100),nullable=False)
    temperature = db.Column(db.Integer, nullable=False)
    weather_description = db.Column(db.String(200), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(5))
    tempmax = db.Column(db.Integer, nullable=True)
    tempmin = db.Column(db.Integer, nullable=True)
    sunrise = db.Column(db.String(50), nullable=True)
    sunset = db.Column(db.String(50), nullable=True)
    wind_speed = db.Column(db.Integer, nullable=True)
    wind_deg = db.Column(db.Integer, nullable=True)
    rainfall = db.Column(db.Integer, nullable=True)
    feels_like = db.Column(db.Integer, nullable=True)
    humidity = db.Column(db.Integer, nullable=True)
    visibility = db.Column(db.Integer, nullable=True)
    pressure = db.Column(db.Integer, nullable=True)
    submission_time = db.Column(db.String(50), default=datetime.now)


class Forecast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    forecast_day = db.Column(db.String(50), nullable=False)
    forecast_symbol = db.Column(db.String(50), nullable=False)
    forecast_name = db.Column(db.String(100), nullable=False)
    forecast_tempmax = db.Column(db.Integer, nullable=False)
    forecast_tempmin = db.Column(db.Integer, nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.now)

class Hourly(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    hourly_time = db.Column(db.String(50), nullable=False)
    hourly_symbol = db.Column(db.String(50), nullable=False)
    hourly_name = db.Column(db.String(100), nullable=False)
    hourly_temp = db.Column(db.Integer, nullable=False)
    hourly_precipitation = db.Column(db.Integer, nullable=False)
    wind_speed = db.Column(db.Integer, nullable=False)
    wind_deg = db.Column(db.Integer, nullable=False)
    wind_symbol = db.Column(db.String(50), nullable=False)
    last_updated = db.Column(db.DateTime, default=datetime.now)

@app.route('/search_results', methods=['GET'])
def search_results():
    #get the query a user is typing and make it lowercase for the database to interpret it
    query = request.args.get('query', '').lower()

    # If query is empty, return no results
    if not query:
        return jsonify({'city_names': []})  # No cities to return
    
    #read the json file
    try:
        file_path = os.path.join(os.path.dirname(__file__), "current.city.list.json")
        with open(file_path, "r", encoding="utf-8") as file:
            cities = json.load(file)

        # Separate prefix matches and substring matches
        prefix_matches = [city["name"] for city in cities if city["name"].lower().startswith(query)]
        substring_matches = [city["name"] for city in cities if query in city["name"].lower() and city["name"] not in prefix_matches]

        # Combine, prioritizing prefix matches
        all_matches = prefix_matches + substring_matches

        # Limit results to 10
        limited_cities = all_matches[:10]

        #return city names using json
        return jsonify({
            'city_names': limited_cities
        })
    
    #errors if the file isn't properly read
    except FileNotFoundError:
        return jsonify({'error': 'City list file not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_max_min(lat, lon):
    #get the first forecast to get the temp max and min for current weather data
    params = {
        'lat': lat,
        'lon': lon,
        'units': 'imperial',
        'exclude': 'current,minutely,hourly,alerts',
        'appid': API_KEY
    }
    response = requests.get(API7_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()
        # Return only the first day's data
        return data['daily'][0]
    else:
        return None
    
def get_current(location):
    params = {
        'q': location,
        'appid': API_KEY,
        'units': 'imperial'
    }
    try:
        #get current weather data 
        response = requests.get(API_URL, params=params)
        data = response.json()
        # set variables to pass to model fields
        if data:
            #convert times to proper format to display on page
            formatted_time = datetime.fromtimestamp(data['dt']).strftime('%-I:%M %p')
            formatted_sunrise = datetime.fromtimestamp(data['sys']['sunrise']).strftime('%-I:%M')
            formatted_sunset = datetime.fromtimestamp(data['sys']['sunset']).strftime('%-I:%M')
            #use get_coordinates to get lat, lon fields for get_max_min function
            coordinates = get_coordinates(location)
            lat, lon = coordinates
            first_day = get_max_min(lat, lon)
            # use get_max_min function to get temp max and min
            forecast_temp_max = int(first_day['temp']['max'])
            forecast_temp_min = int(first_day['temp']['min'])

            # Existing or new location
            existing_location = Location.query.filter_by(city=location).first()
            location_obj = existing_location or Location(city=location)

            # Update or set fields
            location_obj.time = formatted_time
            location_obj.icon = data['weather'][0]['icon']
            location_obj.weather_description = data['weather'][0]['description']
            location_obj.temperature = int(data['main']['temp'])
            location_obj.tempmax = forecast_temp_max
            location_obj.tempmin = forecast_temp_min
            location_obj.sunrise = formatted_sunrise
            location_obj.sunset = formatted_sunset
            location_obj.wind_speed = int(data['wind']['speed'])
            location_obj.wind_deg = int(data['wind']['deg'])
            location_obj.rainfall = int(data.get('rain', {}).get('1h', 0))  # Safely handle missing 'rain' key
            location_obj.feels_like = int(data['main']['feels_like'])
            location_obj.humidity = int(data['main']['humidity'])
            location_obj.visibility = round(data['visibility'] * 0.000621371)
            location_obj.pressure = round(data['main']['pressure'] * 0.02953, 2)
            location_obj.submission_time = datetime.now()

            # if the location doesn't exist add it to the database
            if not existing_location:
                db.session.add(location_obj)

            db.session.commit()

            #return location_obj to pass to view
            return location_obj
     
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to retrieve weather data for {location} - {e}")
    except Exception as e:
        print(f"Error committing to the database: {e}")
        db.session.rollback()
    return None

def update_weather(city=None):
    #Updates weather for all locations or specific city depending on if city is None or not
    locations = (
                Location.query.all() if city is None
                else Location.query.filter_by(city=city).all()
    )

    updated_locations = []

    for location in locations:
        updated_location = get_current(location.city)
        if updated_location:
            updated_locations.append({
                "id": location.id,
                "city": location.city,
                "temperature": updated_location.temperature,
                "weather_description": updated_location.weather_description,
                "time": updated_location.time,
                "icon": updated_location.icon,
                "tempmax": updated_location.tempmax,
                "tempmin": updated_location.tempmin,
                "sunrise": updated_location.sunrise,
                "sunset": updated_location.sunset,
                "wind_speed": updated_location.wind_speed,
                "wind_deg": updated_location.wind_deg,
                "rainfall": updated_location.rainfall,
                "feels_like": updated_location.feels_like,
                "humidity": updated_location.humidity,
                "visibility": updated_location.visibility,
                "pressure": updated_location.pressure,
                "submission_time": updated_location.submission_time
            })
    
    return updated_locations

def get_coordinates(city):
    #get lat and lon attributes to pass to functions in order to get certain data
    params = {
        'q': city,
        'appid': API_KEY,
        'limit': 1
    }
    try:
        response = requests.get(GEO_URL, params=params)
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = data[0]['lat']
                lon = data[0]['lon']
                if lat and lon is not None:
                    return lat, lon
                else:
                    print(f"Error: Incomplete data for {city}")
                    return None 
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to retrieve location data for {city} - {e}")
        return None

    
def get_forecast(location, lat, lon):
        # get forecast data
        params = {
            'lat': lat,
            'lon': lon,
            'units': 'imperial',
            'exclude': 'current,minutely,hourly,alerts',
            'appid': API_KEY
        }
        response = requests.get(API7_URL, params=params)
        
        if response.status_code == 200:
            data = response.json()
            week_data =[]
            for day in data['daily'][:7]:
                forecast_date = date.fromtimestamp(day['dt'])
                formatted_date = forecast_date.strftime('%B %d, %Y')
                forecast_day_name = calendar.day_name[forecast_date.weekday()]
                rainfall = int(day.get('rain', 0))
                #insert new entry
                week_data.append({
                    'city':location,
                    'forecast_day': forecast_day_name,
                    'forecast_date': formatted_date,
                    'forecast_symbol':day['weather'][0]['icon'],
                    'forecast_name':day['weather'][0]['description'],
                    'forecast_tempmax':int(day['temp']['max']),
                    'forecast_tempmin':int(day['temp']['min']),
                    'pressure':round(day['pressure'] * 0.02953, 2),
                    'humidity':int(day['humidity']),
                    'precipitation':int(day['pop'] * 100),
                    'rainfall': rainfall
                })
                    

            try:
                return week_data
            except Exception as e:
                print(f"Error returning data: {e}")

        else:
            print(f"Error: Unable to retrieve forecast data for {location}")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            return None

def get_hourly(location, lat, lon):
        params = {
            'lat': lat,
            'lon': lon,
            'units': 'imperial',
            'exclude': 'current,minutely,daily,alerts',
            'appid': API_KEY
        }
        response = requests.get(API7_URL, params=params)
        
        if response.status_code == 200:
            data = response.json()

            # Save first 24 hours' data to the database
            hourly_data = []
            for hour in data['hourly'][:24]:
                forecast_time = datetime.fromtimestamp(hour['dt']).strftime('%-I:%M %p')
                forecast_hour = forecast_time.replace(':00', '')
                wind_deg = int(hour['wind_deg'])
                # Determine the wind direction image
                if 0 <= wind_deg <= 22.5:
                    wind_image = 'static/Images/north_arrow.png'  # Path to your north arrow image
                elif 22.6 <= wind_deg <= 67.5:
                    wind_image = 'static/Images/northeast_arrow.png'   # Path to your east arrow image
                elif 67.6 <= wind_deg <= 112.5:
                    wind_image = 'static/Images/east_arrow.png'  # Path to your south arrow image
                elif 112.6 <= wind_deg <= 157.5:
                    wind_image = 'static/Images/southeast_arrow.png'   # Path to your west arrow image
                elif 157.6 <= wind_deg < 202.5:
                    wind_image = 'static/Images/south_arrow.png' 
                elif 202.6 <= wind_deg < 247.5:
                    wind_image = 'static/Images/southwest_arrow.png' 
                elif 247.6 <= wind_deg < 292.5:
                    wind_image = 'static/Images/west_arrow.png' 
                elif 292.6 <= wind_deg < 337.5:
                    wind_image = 'static/Images/northwest_arrow.png' 
                elif 337.6 <= wind_deg < 360:
                    wind_image = 'static/Images/north_arrow.png' 
                else:
                    wind_image = 'static/Images/north_arrow.png' # Fallback image
                
                # return hourly data for asynchronus purposes
                hourly_data.append({
                    'city':location,
                    'hourly_time':str(forecast_hour),
                    'hourly_symbol':hour['weather'][0]['icon'],
                    'hourly_name':hour['weather'][0]['description'],
                    'hourly_temp':int(hour['temp']),
                    'hourly_precipitation':int(hour['pop'] * 100),
                    'wind_speed':int(hour['wind_speed']),
                    'wind_deg':int(hour['wind_deg']),
                    'wind_symbol':wind_image,
                    'last_updated':forecast_time
                })
                    

            try:
                return hourly_data
            except Exception as e:
                print(f"Error returning data: {e}")
            

        else:
            print(f"Error: Unable to retrieve forecast data for {location}")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            return None

 
    
@app.route('/delete/<int:id>', methods=['DELETE'])
def delete_location(id):
    try:
        # delete locations by getting that location id and let the database know as well so it doesn't display data later
        deleted_location = Location.query.get(id)
        if deleted_location:
            db.session.delete(deleted_location)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Location deleted successfully' })
        else:
            return jsonify({'success': False, 'message': 'Location not found'}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

#
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data = request.get_json()
        # pass the location from the html page using javascript 
        location = data.get('location', '').strip().title()
        current_weather = get_current(location)
        
        #if no location return erro 
        if current_weather is None:
            return jsonify({'error': 'Failed to retrieve weather data.'}), 400
        
        #if location asynchronously pass data to html page 
        return jsonify ({
                'success': True,
                'id': current_weather.id,
                'city': current_weather.city,
                'time': current_weather.time,
                'icon': current_weather.icon,
                'weather_description': current_weather.weather_description,
                'temperature': current_weather.temperature,
                'tempmax': current_weather.tempmax,
                'tempmin': current_weather.tempmin
        }), 200
    
    else:
        locations = Location.query.order_by(desc(Location.submission_time)).all()
        return render_template("index.html", locations=locations)

# update current weather data 
@app.route('/update')
def update_index_page():
    updated_data = update_weather()
    if not updated_data:
        return jsonify({'error': 'No locations were updated.'}), 400
    return jsonify ({
        'updated_data': updated_data
    }), 200

# get location data including hourly and forecast data 
@app.route('/<location_name>')
def location_page(location_name):
    location_data = get_coordinates(location_name)
    # if there is a valid location, get the hourly and forecast data as well
    if location_data:
        lat,lon = location_data
        forecast_data = get_forecast(location_name, lat, lon)
        hourly_data = get_hourly(location_name, lat, lon)
    else:
        forecast_data = []
        hourly_data = []

    location = Location.query.filter_by(city=location_name).all()
    return render_template("location.html", location=location, forecast=forecast_data, hourly=hourly_data)

#update location page by call update_weather function
@app.route('/update/<location_name>')
def update_location_page(location_name):
    updated_location = update_weather(location_name)
    if not updated_location:
         return jsonify({'error': 'Location was not updated.'}), 400
    
    # asynchronously passes updated forecast and hourly data
    location_data = get_coordinates(location_name)
    
    if location_data:
        lat, lon = location_data
        forecast_data = get_forecast(location_name, lat, lon)
        hourly_data = get_hourly(location_name, lat, lon)
    
    return jsonify({
        'updated_data': updated_location,
        'forecast':forecast_data,
        'hourly': hourly_data
    }), 200 

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
