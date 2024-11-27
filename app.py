from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, desc
from flask_migrate import Migrate
from datetime import datetime, timezone, date, timedelta
import calendar


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
    submission_time = db.Column(db.DateTime, default=datetime.now)

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
            coordinates = get_location(location)
            lat, lon = coordinates
            first_day = first_forecast(location, lat, lon)
            forecast_temp_max = int(first_day['temp']['max'])
            forecast_temp_min = int(first_day['temp']['min'])

            existing_location = Location.query.filter_by(city=location).first()
            if existing_location:
                existing_location.time = formatted_time
                existing_location.icon = data['weather'][0]['icon']
                existing_location.weather_description = data['weather'][0]['description']
                existing_location.temperature = int(data['main']['temp'])
                existing_location.tempmax = forecast_temp_max
                existing_location.tempmin = forecast_temp_min
            else:
                new_location = Location(
                    city = location,
                    time = formatted_time,
                    icon = data['weather'][0]['icon'], 
                    weather_description = data['weather'][0]['description'],  
                    temperature = int(data['main']['temp']),
                    tempmax = forecast_temp_max,
                    tempmin = forecast_temp_min
                )

                db.session.add(new_location)
        
            db.session.commit()
            locationObj = existing_location or new_location
            return {
                'id': locationObj.id,
                'city': location,
                'time': formatted_time,
                'icon': data['weather'][0]['icon'],
                'weather_description': data['weather'][0]['description'],
                'temperature': int(data['main']['temp']),
                'tempmax': forecast_temp_max,
                'tempmin': forecast_temp_min,
            }
     
    except requests.exceptions.RequestException as e:
        print(f"Error: Failed to retrieve weather data for {location} - {e}")
    except Exception as e:
        print(f"Error committing to the database: {e}")
        db.session.rollback()
    return None

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
                update_locations.append ({
                    'id': locations.id,
                    'city': locations.city,
                    'time': locations.time,
                    'icon': locations.icon,
                    'weather_description': locations.weather_description,
                    'temperature': locations.temperature,
                    'tempmax': locations.tempmax,
                    'tempmin': locations.tempmin
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
                formatted_time = datetime.fromtimestamp(day['dt']).strftime('%-I:%M %p')
                forecast_day_name = calendar.day_name[forecast_date.weekday()]
                #insert new entry
                week_data.append({
                    'city':location,
                    'forecast_day': forecast_day_name,
                    'forecast_symbol':day['weather'][0]['icon'],
                    'forecast_name':day['weather'][0]['description'],
                    'forecast_tempmax':int(day['temp']['max']),
                    'forecast_tempmin':int(day['temp']['min']),
                    'last_updated': formatted_time
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
