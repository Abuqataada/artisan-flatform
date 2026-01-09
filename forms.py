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
    

# Add to forms.py

from wtforms import DateField, FileField
from flask_wtf.file import FileRequired, FileAllowed

class ArtisanKYCForm(FlaskForm):
    """Form for artisan KYC verification"""
    nin = StringField('National Identification Number (NIN)', 
                     validators=[DataRequired(), Length(min=11, max=11)],
                     render_kw={"placeholder": "11-digit NIN number"})
    
    date_of_birth = DateField('Date of Birth', validators=[DataRequired()],
                             format='%Y-%m-%d',
                             render_kw={"placeholder": "YYYY-MM-DD"})
    
    nationality = SelectField('Nationality', 
                            validators=[DataRequired()],
                            choices=[
                                ('Nigerian', 'Nigerian'),
                                ('other', 'Other Nationality')
                            ])
    
    state_of_origin = StringField('State of Origin', 
                                 validators=[DataRequired(), Length(min=2, max=100)],
                                 render_kw={"placeholder": "e.g., Lagos, Rivers, etc."})
    
    lga_of_origin = StringField('Local Government Area (LGA)', 
                               validators=[DataRequired(), Length(min=2, max=100)],
                               render_kw={"placeholder": "Your Local Government Area"})
    
    # Bank Information
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
        ('wema', 'Wema Bank'),
        ('sterling', 'Sterling Bank'),
        ('other', 'Other')
    ])
    
    account_name = StringField('Account Name', 
                              validators=[DataRequired(), Length(min=2, max=100)],
                              render_kw={"placeholder": "As it appears on bank statement"})
    
    account_number = StringField('Account Number', 
                                validators=[DataRequired(), Length(min=10, max=10)],
                                render_kw={"placeholder": "10-digit account number"})
    
    # Document Uploads
    nin_front_image = FileField('NIN Front Image', 
                               validators=[
                                   FileRequired(),
                                   FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDFs only!')
                               ])
    
    nin_back_image = FileField('NIN Back Image (Optional)', 
                              validators=[
                                  FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDFs only!')
                              ])
    
    passport_photo = FileField('Passport Photograph', 
                              validators=[
                                  FileRequired(),
                                  FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')
                              ])
    
    proof_of_address = FileField('Proof of Address', 
                                validators=[
                                    FileRequired(),
                                    FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDFs only!')
                                ])
    
    other_documents = FileField('Other Verification Documents (Optional)', 
                               validators=[
                                   FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Images and PDFs only!')
                               ])
    
    # Terms and conditions
    certify_truth = BooleanField('I certify that all information provided is true and accurate',
                                validators=[DataRequired()])
    
    authorize_verification = BooleanField('I authorize Uwaila Global to verify my KYC details',
                                         validators=[DataRequired()])
    
    submit = SubmitField('Submit for Verification')
    
    def validate(self, extra_validators=None):
        """Custom validation for NIN"""
        initial_validation = super(ArtisanKYCForm, self).validate()
        if not initial_validation:
            return False
        
        # Validate NIN format (11 digits)
        if not self.nin.data.isdigit() or len(self.nin.data) != 11:
            self.nin.errors.append('NIN must be 11 digits')
            return False
        
        # Validate account number (10 digits)
        if not self.account_number.data.isdigit() or len(self.account_number.data) != 10:
            self.account_number.errors.append('Account number must be 10 digits')
            return False
        
        # Validate date of birth (must be at least 18 years old)
        if self.date_of_birth.data:
            from datetime import date
            today = date.today()
            age = today.year - self.date_of_birth.data.year - (
                (today.month, today.day) < (self.date_of_birth.data.month, self.date_of_birth.data.day)
            )
            if age < 18:
                self.date_of_birth.errors.append('You must be at least 18 years old')
                return False
        
        return True