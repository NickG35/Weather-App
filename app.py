from flask import Flask, render_template, request
import requests
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime, timezone


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///locations.db'
app.config['TEMPLATES_AUTO_RELOAD'] = True

#initiate database
db=SQLAlchemy(app)
migrate = Migrate(app, db)

#API endpoint and key
API_KEY = 'c24adc3699d398ec4a13585f3590d00e'
API_URL = 'http://api.openweathermap.org/data/2.5/weather'
API7_URL = "http://api.openweathermap.org/data/2.5/forecast/daily"

#create models for db
class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    temperature = db.Column(db.Float, nullable=False)
    weather_description = db.Column(db.String(200), nullable=False)
    time = db.Column(db.DateTime, default = datetime.now(timezone.utc))
    icon = db.Column(db.String(5))

class Forecast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(100), nullable=False)
    forecast_day = db.Column(db.String(50), nullable=False)
    forecast_symbol = db.Column(db.String(50), nullable=False)
    forecast_name = db.Column(db.String(100), nullable=False)
    forecast_tempmax = db.Column(db.Float, nullable=False)
    forecast_tempmin = db.Column(db.Float, nullable=False)

def get_weather(location):
    params = {
        'q': location,
        'appid': API_KEY,
        'units': 'metric'
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
    
 def get_forecast(location):
    params = {
        'q': location,
        'appid': API_KEY,
        'units': 'metric',
        'cnt': '7'
    }
    response = requests.get(API_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        # save data to the database
        new_forecast = Forecast(
                city = data['name'],
        )
        db.session.add(new_forecast)
        db.session.commit()
        return data

    else:
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
    location = Location.query.filter_by(city=location_name).all()
    return render_template("location.html", location=location)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
