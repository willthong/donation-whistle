from flask_wtf import FlaskForm
from wtforms import SubmitField

class DBImport(FlaskForm):
    submit = SubmitField("Import data from Electoral Commission")
    
