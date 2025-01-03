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
    query = request.args.get('query', '').lower()

    # If query is empty, return no results
    if not query:
        return jsonify({'city_names': []})  # No cities to return
    
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

        return jsonify({
            'city_names': limited_cities
        })
    
    except FileNotFoundError:
        return jsonify({'error': 'City list file not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500



def get_current(location):
    params = {
        'q': location,
        'appid': API_KEY,
        'units': 'imperial'
    }
    try:
        response = requests.get(API_URL, params=params)
        data = response.json()
        if data:
            formatted_time = datetime.fromtimestamp(data['dt']).strftime('%-I:%M %p')
            formatted_sunrise = datetime.fromtimestamp(data['sys']['sunrise']).strftime('%-I:%M')
            formatted_sunset = datetime.fromtimestamp(data['sys']['sunset']).strftime('%-I:%M')
            coordinates = get_location(location)
            lat, lon = coordinates
            first_day = first_forecast(location, lat, lon)
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

            if not existing_location:
                db.session.add(location_obj)

            db.session.commit()

            return {
                'id': location_obj.id,
                'city': location,
                'time': formatted_time,
                'icon': data['weather'][0]['icon'],
                'weather_description': data['weather'][0]['description'],
                'temperature': int(data['main']['temp']),
                'tempmax': forecast_temp_max,
                'tempmin': forecast_temp_min,
                'sunrise' : formatted_sunrise,
                'sunset' : formatted_sunset,
                'wind_speed': int(data['wind']['speed']),
                'wind_deg': int(data['wind']['deg']),
                'rainfall': int(data.get('rain', {}).get('1h', 0)),  # Safely handle missing 'rain' key
                'feels_like' : int(data['main']['feels_like']),
                'humidity' : int(data['main']['humidity']),
                'visibility' : round(data['visibility'] * 0.000621371),
                'pressure' : round(data['main']['pressure'] * 0.02953, 2),
                'submission_time': datetime.now()
            }
     
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to retrieve weather data for {location} - {e}")
    except Exception as e:
        print(f"Error committing to the database: {e}")
        db.session.rollback()
    return None

def update_location(location):
    existing_location = Location.query.filter_by(city=location).all()
    update_locations = []
    for location in existing_location:
        try:
            new_weather = get_current(location.city)
            if new_weather:
                location.time = new_weather['time']
                location.icon = new_weather['icon']
                location.weather_description = new_weather['weather_description']
                location.temperature = new_weather['temperature']
                location.tempmax = new_weather['tempmax']
                location.tempmin = new_weather['tempmin']
                location.sunrise = new_weather['sunrise']
                location.sunset = new_weather['sunset']
                location.wind_speed = new_weather['wind_speed']
                location.wind_deg = new_weather['wind_deg']
                location.rainfall = new_weather['rainfall']
                location.feels_like = new_weather['feels_like']
                location.humidity = new_weather['humidity']
                location.visibility = new_weather['visibility']
                location.pressure = new_weather['pressure']
                location.submission_time = new_weather['submission_time']
                update_locations.append ({
                    'id': location.id,
                    'city': location.city,
                    'time': location.time,
                    'icon': location.icon,
                    'weather_description': location.weather_description,
                    'temperature': location.temperature,
                    'tempmax': location.tempmax,
                    'tempmin': location.tempmin,
                    'sunrise': location.sunrise, 
                    'sunset': location.sunset, 
                    'wind_speed': location.wind_speed,
                    'wind_deg': location.wind_deg, 
                    'rainfall': location.rainfall, 
                    'feels_like': location.feels_like,
                    'humidity': location.humidity,
                    'visibility': location.visibility,
                    'pressure': location.pressure,
                    'submission_time': location.submission_time
                })
        except Exception as e:
            print(f"Error updating location {location.city}: {e}")
    try:
        db.session.commit()
    except Exception as e:
        print(f"Error committing updates to databse: {e}")
    
    return update_locations


def update_current():
    existing_locations = Location.query.all()
    update_locations = []
    for locations in existing_locations:
        try:
            new_weather = get_current(locations.city)
            if new_weather:
                locations.time = new_weather['time']
                locations.icon = new_weather['icon']
                locations.weather_description = new_weather['weather_description']
                locations.temperature = new_weather['temperature']
                locations.tempmax = new_weather['tempmax']
                locations.tempmin = new_weather['tempmin']
                locations.sunrise = new_weather['sunrise']
                locations.sunset = new_weather['sunset']
                locations.wind_speed = new_weather['wind_speed']
                locations.wind_deg = new_weather['wind_deg']
                locations.rainfall = new_weather['rainfall']
                locations.feels_like = new_weather['feels_like']
                locations.humidity = new_weather['humidity']
                locations.visibility = new_weather['visibility']
                locations.pressure = new_weather['pressure']
                locations.submission_time = new_weather['submission_time']
                update_locations.append ({
                    'id': locations.id,
                    'city': locations.city,
                    'time': locations.time,
                    'icon': locations.icon,
                    'weather_description': locations.weather_description,
                    'temperature': locations.temperature,
                    'tempmax': locations.tempmax,
                    'tempmin': locations.tempmin,
                    'sunrise': locations.sunrise, 
                    'sunset': locations.sunset, 
                    'wind_speed': locations.wind_speed,
                    'wind_deg': locations.wind_deg, 
                    'rainfall': locations.rainfall, 
                    'feels_like': locations.feels_like,
                    'humidity': locations.humidity,
                    'visibility': locations.visibility,
                    'pressure': locations.pressure,
                    'submission_time': locations.submission_time
                })
        except Exception as e:
            print(f"Error updating location {locations.city}: {e}")
    try:
        db.session.commit()
    except Exception as e:
        print(f"Error committing updates to databse: {e}")
    
    return update_locations

                

def get_location(city):
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
        #otherwise fetch new data
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

def first_forecast(location, lat, lon):
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
        # try to do id to use the get not filter_by for tomorrow
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

#figured out why the submissions duplicate, im making new entries for the get forecast and get weather, make a new view to just get the temp max and min.
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data = request.get_json()
        location = data.get('location', '').strip().title()
        current_weather = get_current(location)

        if current_weather is None:
            return jsonify({'error': 'Failed to retrieve weather data.'}), 400
               
        return jsonify ({
                'success': True,
                'id': current_weather['id'],
                'city': current_weather['city'],
                'time': current_weather['time'],
                'icon': current_weather['icon'],
                'weather_description': current_weather['weather_description'],
                'temperature': current_weather['temperature'],
                'tempmax': current_weather['tempmax'],
                'tempmin': current_weather['tempmin'],
        }), 200
    
    else:
        locations = Location.query.order_by(desc(Location.submission_time)).all()
        return render_template("index.html", locations=locations)
    
@app.route('/update/<location_name>')
def update_locpage(location_name):
    updated_location = update_location(location_name)
    if not updated_location:
         return jsonify({'error': 'Location was not updated.'}), 400
    return jsonify({
        'updated_data': updated_location
    }), 200 

@app.route('/update')
def update_page():
    updated_data = update_current()
    if not updated_data:
        return jsonify({'error': 'No locations were updated.'}), 400
    return jsonify ({
        'updated_data': updated_data
    }), 200

@app.route('/<location_name>')
def location_page(location_name):
    location_data = get_location(location_name)
    if location_data:
        lat,lon = location_data
        forecast_data = get_forecast(location_name, lat, lon)
        hourly_data = get_hourly(location_name, lat, lon)
    else:
        forecast_data = []
        hourly_data = []

    location = Location.query.filter_by(city=location_name).all()
    return render_template("location.html", location=location, forecast=forecast_data, hourly=hourly_data)

@app.route('/api/<location_name>')
def api_weather(location_name):
    location_data = get_location(location_name)
    
    if location_data:
        lat, lon = location_data
        forecast_data = get_forecast(location_name, lat, lon)
        hourly_data = get_hourly(location_name, lat, lon)
        return jsonify(forecast=forecast_data, hourly=hourly_data)
    
    else:
        return jsonify(error="Location not found"), 404

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
