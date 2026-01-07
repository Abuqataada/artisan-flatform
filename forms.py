# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, ValidationError
from models import User

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Sign In')
    
    def validate_email(self, email):
        # Check if user exists in any of the tables
        user = User.query.filter_by(email=email.data).first()
        artisan = User.query.filter_by(email=email.data, user_type='artisan').first()
        admin = User.query.filter_by(email=email.data, user_type='admin').first()
        
        if not user and not artisan and not admin:
            raise ValidationError('Email not registered.')

class UserRegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired()])
    address = StringField('Address', validators=[Length(max=200)])
    submit = SubmitField('Create Account')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')

class ArtisanRegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15)])
    category = StringField('Service Category', validators=[DataRequired()])
    skills = StringField('Skills & Specializations', validators=[DataRequired()])
    experience_years = StringField('Years of Experience', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired()])
    submit = SubmitField('Submit for Verification')
    
    def validate_email(self, email):
        artisan = User.query.filter_by(email=email.data, user_type='artisan').first()
        if artisan:
            raise ValidationError('Email already registered.')