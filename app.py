from flask import Flask, render_template, request
import requests
from flask_sqlalchemy import SQLAlchemy
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
    time = db.Column(db.DateTime, default = datetime.now(timezone.utc))
    icon = db.Column(db.String(5))

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
    hour = db.Column(db.String(50), nullable=False)
    hourly_symbol = db.Column(db.String(50), nullable=False)
    hourly_name = db.Column(db.String(100), nullable=False)
    hourly_temp = db.Column(db.Integer, nullable=False)

def get_weather(location):
    params = {
        'q': location,
        'appid': API_KEY,
        'units': 'imperial'
    }
    response = requests.get(API_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        # save data to the database
        new_location = Location(
                city = data['name'],
                temperature = data['main']['temp'],
                weather_description = data['weather'][0]['description'],
                icon = data['weather'][0]['icon']
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
            forecast_day_name = calendar.day_name[forecast_date.weekday()]\
            
            existing_forecast = Forecast.query.filter_by(city=location, forecast_day=forecast_day_name)
            if not existing_forecast:
                new_forecast = Forecast(
                    city=location,
                    forecast_day=forecast_day_name,
                    forecast_symbol=day['weather'][0]['icon'],
                    forecast_name=day['weather'][0]['description'],
                    forecast_tempmax=day['temp']['max'],
                    forecast_tempmin=day['temp']['min']
                )
                db.session.add(new_forecast)
                db.session.commit()
                return data
            else:
                return None

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

        # Save first 24 hours' data to the database
        for hour in data['hourly'][:24]:
            forecast_hour =datetime.fromtimestamp(hour['dt']).hour
            
            existing_hourly = Hourly.query.filter_by(city=location, hour=forecast_hour)
            if not existing_hourly:
                new_hourly = Hourly(
                    city=location,
                    hour=str(forecast_hour),
                    hourly_symbol=hour['weather'][0]['icon'],
                    hourly_name=hour['weather'][0]['description'],
                    hourly_temp=hour['temp']
                )
                db.session.add(new_hourly)

        db.session.commit()
        return data

    else:
        print(f"Error: Unable to retrieve forecast data for {location}")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        return None

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        #get_weather function runs with the city that is entered in form
        location = request.form['location']
        get_weather(location)

    #query all locations to display on page 
    locations = Location.query.all()
    return render_template("index.html", locations=locations)

@app.route('/<location_name>')
def location_page(location_name):
    location_data = get_location(location_name)
    if location_data:
        lat, lon = location_data
        get_forecast(location_name, lat, lon)
        get_hourly(location_name, lat, lon)
        print(f"Latitude: {lat}, Longitude: {lon}")
        forecast = Forecast.query.filter_by(city=location_name).all()
        hourly = Hourly.query.filter_by(city=location_name).all()
    else:
        forecast = []
        hourly = []
    location = Location.query.filter_by(city=location_name).all()
    return render_template("location.html", location=location, forecast=forecast, hourly=hourly)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
