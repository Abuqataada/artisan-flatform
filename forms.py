# forms.py
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Email, Length, ValidationError
from models import User
from wtforms import StringField, PasswordField, TextAreaField, SelectField, DecimalField, FileField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from flask_wtf.file import FileAllowed

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
        


# In forms.py, add:

from wtforms import StringField, TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired, Length, Optional
from datetime import datetime

class ServiceRequestForm(FlaskForm):
    """Form for creating service requests"""
    title = StringField('Service Title', validators=[
        DataRequired(),
        Length(min=5, max=200)
    ])
    category_id = SelectField('Service Category', 
                            choices=[],  # Will be populated dynamically
                            validators=[DataRequired()])
    description = TextAreaField('Description', validators=[
        DataRequired(),
        Length(min=20, max=1000)
    ])
    location = StringField('Location', validators=[
        DataRequired(),
        Length(min=5, max=200)
    ])
    preferred_date = DateField('Preferred Date', 
                             validators=[Optional()],
                             format='%Y-%m-%d',
                             default=datetime.today)
    preferred_time = SelectField('Preferred Time', 
                               choices=[
                                   ('', 'Any time'),
                                   ('Morning (8am-12pm)', 'Morning (8am-12pm)'),
                                   ('Afternoon (12pm-4pm)', 'Afternoon (12pm-4pm)'),
                                   ('Evening (4pm-8pm)', 'Evening (4pm-8pm)'),
                                   ('Flexible', 'Flexible')
                               ],
                               validators=[Optional()])
    additional_notes = TextAreaField('Additional Notes',
                                   validators=[
                                       Optional(),
                                       Length(max=500)
                                   ])
    submit = SubmitField('Submit Request')


# forms.py - Add these forms

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, SelectField, DecimalField, FileField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from flask_wtf.file import FileAllowed

class BankAccountForm(FlaskForm):
    """Form for adding/updating bank account details"""
    bank_name = SelectField('Bank Name', validators=[DataRequired()], choices=[
        ('', 'Select Bank'),
        ('zenith', 'Zenith Bank'),
        ('gtb', 'GTBank'),
        ('access', 'Access Bank'),
        ('first', 'First Bank'),
        ('uba', 'UBA'),
        ('fidelity', 'Fidelity Bank'),
        ('stanbic', 'Stanbic IBTC'),
        ('union', 'Union Bank'),
        ('ecobank', 'Ecobank'),
        ('polaris', 'Polaris Bank'),
        ('other', 'Other')
    ])
    account_name = StringField('Account Name', validators=[DataRequired(), Length(min=2, max=100)])
    account_number = StringField('Account Number', validators=[DataRequired(), Length(min=10, max=10)])
    other_bank_name = StringField('Other Bank Name', validators=[Optional(), Length(min=2, max=100)])
    submit = SubmitField('Save Bank Details')


class PaymentForm(FlaskForm):
    """Form for making payments"""
    payment_method = SelectField('Payment Method', validators=[DataRequired()], choices=[
        ('cash', 'Cash Payment'),
        ('bank_transfer', 'Bank Transfer'),
        ('paystack', 'Paystack (Coming Soon)')
    ])
    amount = DecimalField('Amount (₦)', validators=[DataRequired()])
    payer_account_name = StringField('Your Account Name', validators=[Optional(), Length(min=2, max=100)])
    payer_account_number = StringField('Your Account Number', validators=[Optional(), Length(min=10, max=10)])
    payer_bank_name = StringField('Your Bank Name', validators=[Optional(), Length(min=2, max=100)])
    transaction_reference = StringField('Transaction Reference', validators=[Optional(), Length(min=5, max=50)])
    payment_notes = TextAreaField('Payment Notes (Optional)', validators=[Optional(), Length(max=500)])
    receipt_image = FileField('Upload Payment Receipt (Optional)', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDFs only!')
    ])
    submit = SubmitField('Submit Payment')
    
    def validate(self, extra_validators=None):
        """Custom validation for bank transfer"""
        initial_validation = super(PaymentForm, self).validate()
        if not initial_validation:
            return False
        
        # Additional validation for bank transfer
        if self.payment_method.data == 'bank_transfer':
            if not self.payer_account_name.data:
                self.payer_account_name.errors.append('Account name is required for bank transfer')
                return False
            if not self.payer_account_number.data:
                self.payer_account_number.errors.append('Account number is required for bank transfer')
                return False
            if not self.payer_bank_name.data:
                self.payer_bank_name.errors.append('Bank name is required for bank transfer')
                return False
        
        return True