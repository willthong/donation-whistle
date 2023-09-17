from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired 

from app.models import DonorAlias

class NewAliasName(FlaskForm):
    alias_name = StringField("New alias name", validators=[DataRequired()])
    note = StringField("Notes")
    submit = SubmitField("Save alias")
    
class EditAlias(FlaskForm):
    alias_name = StringField("New alias name", validators=[DataRequired()])
    note = StringField("Notes")
    submit = SubmitField("Save alias")
    
class DeleteAlias(FlaskForm):
    submit = SubmitField("Confirm alias deletion")
    
