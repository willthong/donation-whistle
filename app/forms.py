from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError

from app import db
from app.models import User, DonorAlias

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log in")

class RegistrationForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    email = StringField("Email", validators=[DataRequired(), Email()])
    is_admin = BooleanField("Is administrator?")
    password = PasswordField("Password", validators=[DataRequired()])
    repeat_password = PasswordField(
        "Repeat password", 
        validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Register new user")

    def validate_username(self, username):
        query = db.select(User).filter_by(username=username.data)
        user = db.session.execute(query).scalars().first()
        if user is not None:
            raise ValidationError("That username is taken. Please use a different one.")

    def validate_email(self, email):
        query = db.select(User).filter_by(email=email.data)
        user = db.session.execute(query).scalars().first()
        if user is not None:
            raise ValidationError("That email is taken. Please use a different one.")

class NewAliasName(FlaskForm):
    alias_name = StringField("New alias name", validators=[DataRequired()])
    note = StringField("Notes")
    submit = SubmitField("Save alias")
    
