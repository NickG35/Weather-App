from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime


app = Flask(__name__)
app.config['SQLALCHEMY_DATABSE_URI'] = 'sqlite:///locations.db'

#initiate database
db=SQLAlchemy(app)

#create models for db
class Locations(db.Model):

@app.route('/')
def index():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)
