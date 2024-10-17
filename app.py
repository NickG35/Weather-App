from flask import Flask, render_template, request, redirect, url_for, jsonify
import requests
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_migrate import Migrate
from datetime import datetime, timezone, date
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
    city = db.Column(db.String(100), nullable=False)
    temperature = db.Column(db.Integer, nullable=False)
    weather_description = db.Column(db.String(200), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(5))
    tempmax = db.Column(db.Integer, nullable=True)
    tempmin = db.Column(db.Integer, nullable=True)

class Forecast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    forecast_day = db.Column(db.String(50), nullable=False)
    forecast_symbol = db.Column(db.String(50), nullable=False)
    forecast_name = db.Column(db.String(100), nullable=False)
    forecast_tempmax = db.Column(db.Integer, nullable=False)
    forecast_tempmin = db.Column(db.Integer, nullable=False)

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

def get_weather(location):
    params = {
        'q': location,
        'appid': API_KEY,
        'units': 'imperial'
    }
    response = requests.get(API_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        formatted_time = datetime.fromtimestamp(data['dt']).strftime('%-I:%M %p')
        # save data to the database
        new_location = Location(
                city = data['name'],
                temperature = int(data['main']['temp']),
                weather_description = data['weather'][0]['description'],
                icon = data['weather'][0]['icon'],
                time = str(formatted_time)
        )
        db.session.add(new_location)
        db.session.commit()
        return data

    else:
        return None

def get_location(city):
    params = {
        'q': city,
        'appid': API_KEY,
        'limit': 1
    }
    response = requests.get(GEO_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        if data:
            lat = data[0]['lat']
            lon = data[0]['lon']
            return lat, lon
        else:
            return None
    else:
        print(f"Error: Failed to retrieve location data for {city}")
        return None
    
def get_forecast(location, lat, lon):
    params = {
        'lat': lat,
        'lon': lon,
        'units': 'imperial',
        'exclude': 'current,minutely,hourly,alerts',
        'appid': API_KEY
    }
    print(f"Requesting forecast for: {params}")
    response = requests.get(API7_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()

        # Save first 7 days' data to the database
        for day in data['daily'][:7]:
            forecast_date = date.fromtimestamp(day['dt'])
            forecast_day_name = calendar.day_name[forecast_date.weekday()]
            
            existing_forecast = Forecast.query.filter_by(city=location, forecast_day=forecast_day_name).first()
            if not existing_forecast:
                new_forecast = Forecast(
                    city=location,
                    forecast_day=forecast_day_name,
                    forecast_symbol=day['weather'][0]['icon'],
                    forecast_name=day['weather'][0]['description'],
                    forecast_tempmax=int(day['temp']['max']),
                    forecast_tempmin=int(day['temp']['min'])
                )
                db.session.add(new_forecast)
                print(f"Saving new forecast for {location} on {forecast_day_name}: max {day['temp']['max']}, min {day['temp']['min']}")

        try:
            db.session.commit()
            return data
        except Exception as e:
            print(f"Error commmitting to the database: {e}")
            db.session.rollback()

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
    print(f"Requesting hourly for: {params}")
    response = requests.get(API7_URL, params=params)
    
    if response.status_code == 200:
        data = response.json()
        print(data)

        # Save first 24 hours' data to the database
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
            
            existing_hourly = Hourly.query.filter_by(city=location, hourly_time=str(forecast_hour)).first()
            if not existing_hourly:
                new_hourly = Hourly(
                    city=location,
                    hourly_time=str(forecast_hour),
                    hourly_symbol=hour['weather'][0]['icon'],
                    hourly_name=hour['weather'][0]['description'],
                    hourly_temp=int(hour['temp']),
                    hourly_precipitation=int(hour['pop'] * 100),
                    wind_speed=int(hour['wind_speed']),
                    wind_deg=int(hour['wind_deg']),
                    wind_symbol=wind_image
                )
                db.session.add(new_hourly)
                print(f"Saving new hourly forecast for {location} at {forecast_hour}: temp {hour['temp']}")

        try:
            db.session.commit()
            return data
        except Exception as e:
            print(f"Error commmitting to the database: {e}")
            db.session.rollback()
        

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


@app.route('/', methods=['GET', 'POST'])
def index():
    forecast = None
    if request.method == 'POST':
        #get_weather function runs with the city that is entered in form
        location = request.form['location'].strip().title()
        get_weather(location)
        if location:
            location_data = get_location(location)
            lat, lon = location_data
            get_forecast(location, lat, lon)
            forecast = Forecast.query.filter_by(city=location).first()
            new_location = Location.query.filter(func.lower(Location.city) == location.lower()).first()
            if new_location:
                new_location.tempmax = forecast.forecast_tempmax
                new_location.tempmin = forecast.forecast_tempmin
                db.session.commit()
            else:
                print(f'No location found for: {location}')   
        return redirect(url_for('index'))     

    #query all locations to display on page 
    locations = Location.query.all()
    return render_template("index.html", locations=locations, forecast=forecast)

@app.route('/<location_name>')
def location_page(location_name):
    location_data = get_location(location_name)
    if location_data:
        lat, lon = location_data
        get_forecast(location_name, lat, lon)
        get_hourly(location_name, lat, lon)
        forecast = Forecast.query.filter_by(city=location_name).all()
        hourly = Hourly.query.filter_by(city=location_name).all()
        print("Forecast from DB:", forecast)
        print("Hourly from DB:", hourly)            
    else:
        forecast = []
        hourly = []

    location = Location.query.filter_by(city=location_name).all()
    return render_template("location.html", location=location, forecast=forecast, hourly=hourly)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
