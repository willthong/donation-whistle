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
    
class EditAlias(FlaskForm):
    alias_name = StringField("New alias name", validators=[DataRequired()])
    note = StringField("Notes")
    submit = SubmitField("Save alias")
    
class DeleteAlias(FlaskForm):
    submit = SubmitField("Confirm alias deletion")
    
class FilterForm(FlaskForm):
    recipient_labour_party = BooleanField("Labour Party")
    recipient_conservative_and_unionist_party = BooleanField("Conservative Party")
    recipient_liberal_democrats = BooleanField("Liberal Democrats")
    recipient_scottish_national_party = BooleanField("SNP")
    recipient_green_party = BooleanField("Green Party")
    donor_type_individual = BooleanField("Individual")
    donor_type_company = BooleanField("Company")
    donor_type_trade_union = BooleanField("Trade Union")
    donor_type_unincorporated_association = BooleanField("Unincorporated Association")
    donor_type_other = BooleanField("Other")
    donor_type_building_society = BooleanField("Building Society")
    donor_type_public_fund = BooleanField("Public Fund")
    donor_type_limited_liability_partnership = BooleanField("LLP")
    donor_type_trust = BooleanField("Trust")
    donor_type_friendly_society = BooleanField("Friendly Society")
    donor_type_impermissible_donor = BooleanField("Impermissible Donor")
    donor_type_na = BooleanField("N/A")
    donor_type_unidentifiable_donor = BooleanField("Unidentifiable Donor")
    donation_type_cash = BooleanField("Cash")
    donation_type_non_cash = BooleanField("Non Cash")
    donation_type_visit = BooleanField("Visit")
    donation_type_public_funds = BooleanField("Public Funds")
    donation_type_exempt_trust = BooleanField("Exempt Trust")
    donation_type_permissible_donor_exempt_trust = BooleanField("Permissible Donor Exempt Trust")
    donation_type_impermissible_donor = BooleanField("Impermissible Donor")
    donation_type_unidentified_donor = BooleanField("Unidentified Donor")
    is_legacy_true = BooleanField("Legacy")
    is_legacy_false = BooleanField("In vitro")
    submit = SubmitField("Apply filters")
# TODO: work out how to create an Other field with a hover-over
