# models.py - COMPLETELY FIXED VERSION

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import json

db = SQLAlchemy()

def generate_uuid():
    return str(uuid.uuid4())

class User(UserMixin, db.Model):
    """Unified User Model with Roles"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'customer', 'artisan', 'admin'
    nin = db.Column(db.String(50), unique=True)  # National Identification Number
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Common fields for all users
    address = db.Column(db.Text)
    profile_image = db.Column(db.String(255))
    
    # Profile relationships (one-to-one)
    artisan_profile = db.relationship('ArtisanProfile', backref='user', uselist=False, lazy=True)
    admin_profile = db.relationship('AdminProfile', backref='user', uselist=False, lazy=True)
    
    # Relationships are now handled in individual models with explicit foreign_keys
    # No ambiguous relationships here
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_customer(self):
        return self.user_type == 'customer'
    
    @property
    def is_artisan(self):
        return self.user_type == 'artisan'
    
    @property
    def is_admin(self):
        return self.user_type == 'admin'
    
    def to_dict(self):
        base_dict = {
            'id': self.id,
            'email': self.email,
            'phone': self.phone,
            'full_name': self.full_name,
            'user_type': self.user_type,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        # Add profile-specific data
        if self.is_artisan and self.artisan_profile:
            base_dict.update(self.artisan_profile.to_dict())
        elif self.is_admin and self.admin_profile:
            base_dict.update(self.admin_profile.to_dict())
        
        return base_dict

class ArtisanProfile(db.Model):
    """Artisan-specific profile information"""
    __tablename__ = 'artisan_profiles'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # Artisan-specific fields
    category = db.Column(db.String(50), nullable=False)
    skills = db.Column(db.Text)
    credentials = db.Column(db.Text)  # JSON string of certifications
    experience_years = db.Column(db.Integer, default=0)
    availability = db.Column(db.String(20), default='available')  # available, busy, offline
    rating = db.Column(db.Float, default=0.0)
    total_jobs = db.Column(db.Integer, default=0)
    completed_jobs = db.Column(db.Integer, default=0)
    portfolio_images = db.Column(db.Text)  # JSON array of image paths
    hourly_rate = db.Column(db.Float)
    min_service_fee = db.Column(db.Float, default=0.0)
    
    # Financial fields
    total_earnings = db.Column(db.Float, default=0.0)
    pending_balance = db.Column(db.Float, default=0.0)
    available_balance = db.Column(db.Float, default=0.0)
    
    def to_dict(self):
        return {
            'category': self.category,
            'skills': self.skills,
            'experience_years': self.experience_years,
            'availability': self.availability,
            'rating': self.rating,
            'total_jobs': self.total_jobs,
            'completed_jobs': self.completed_jobs,
            'hourly_rate': self.hourly_rate,
            'total_earnings': self.total_earnings,
            'available_balance': self.available_balance
        }

class AdminProfile(db.Model):
    """Admin-specific profile information"""
    __tablename__ = 'admin_profiles'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # Admin-specific fields
    username = db.Column(db.String(50), unique=True, nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    department = db.Column(db.String(100))
    permissions = db.Column(db.Text)  # JSON string of permissions
    
    def to_dict(self):
        return {
            'username': self.username,
            'is_super_admin': self.is_super_admin,
            'department': self.department
        }

class ServiceCategory(db.Model):
    """Service Categories Model"""
    __tablename__ = 'service_categories'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    icon = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'is_active': self.is_active
        }

# In models.py, update the ServiceRequest model
class ServiceRequest(db.Model):
    """Service Request Model"""
    __tablename__ = 'service_requests'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    artisan_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True)
    category_id = db.Column(db.String(36), db.ForeignKey('service_categories.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    preferred_date = db.Column(db.Date)
    preferred_time = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')
    
    # Payment preferences
    payment_method = db.Column(db.String(50), default='cash')
    payment_status = db.Column(db.String(20), default='pending')
    price_estimate = db.Column(db.Float)
    actual_price = db.Column(db.Float)
    
    # Other fields remain the same
    admin_notes = db.Column(db.Text)
    rating = db.Column(db.Integer)
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # Relationships
    client = db.relationship('User', foreign_keys=[user_id], backref='client_requests', lazy=True)
    assigned_artisan = db.relationship('User', foreign_keys=[artisan_id], backref='assigned_requests', lazy=True)
    category_obj = db.relationship('ServiceCategory', backref='service_requests', lazy=True)
    
    @property
    def category(self):
        """Property to get category (for backward compatibility)"""
        return self.category_obj
    
    @property
    def category_name(self):
        """Property to get category name"""
        return self.category_obj.name if self.category_obj else None
    
    @property
    def category_icon(self):
        """Property to get category icon"""
        return self.category_obj.icon if self.category_obj else 'tools'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'price_estimate': self.price_estimate,
            'actual_price': self.actual_price,
            'location': self.location,
            'preferred_date': self.preferred_date.isoformat() if self.preferred_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'category_name': self.category_name,
            'category_id': self.category_id,
            'category_icon': self.category_icon,
            'artisan_name': self.assigned_artisan.full_name if self.assigned_artisan else None,
            'artisan_id': self.artisan_id
        }
    
class Notification(db.Model):
    """Notification System Model"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(50))
    related_id = db.Column(db.String(36))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationship with explicit foreign_key
    user = db.relationship('User', foreign_keys=[user_id], backref='user_notifications', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'notification_type': self.notification_type,
            'related_id': self.related_id
        }

class AccountDeactivation(db.Model):
    """Track account deactivations"""
    __tablename__ = 'account_deactivations'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.Text)
    deactivated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    reactivated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_permanent = db.Column(db.Boolean, default=False)
    
    # Relationship with explicit foreign_key
    user = db.relationship('User', foreign_keys=[user_id], backref='user_deactivations', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'reason': self.reason,
            'deactivated_at': self.deactivated_at.isoformat() if self.deactivated_at else None,
            'reactivated_at': self.reactivated_at.isoformat() if self.reactivated_at else None,
            'is_permanent': self.is_permanent
        }

class VerificationRequest(db.Model):
    """Track verification requests"""
    __tablename__ = 'verification_requests'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    request_data = db.Column(db.Text)  # JSON string with verification data
    admin_notes = db.Column(db.Text)
    reviewed_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships with explicit foreign_keys
    user = db.relationship('User', foreign_keys=[user_id], backref='user_verifications', lazy=True)
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_verifications', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'status': self.status,
            'request_data': json.loads(self.request_data) if self.request_data else None,
            'admin_notes': self.admin_notes,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class UserSettings(db.Model):
    """Store user preferences and settings"""
    __tablename__ = 'user_settings'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    settings_type = db.Column(db.String(50), nullable=False)  # 'notifications', 'privacy', 'appearance'
    settings_data = db.Column(db.Text)  # JSON string with settings
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationship with explicit foreign_key
    user = db.relationship('User', foreign_keys=[user_id], backref='user_settings_list', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'settings_type': self.settings_type,
            'settings_data': json.loads(self.settings_data) if self.settings_data else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
class Withdrawal(db.Model):
    """
    Docstring for Withdrawal
    """
    __tablename__ = 'withdrawals'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    artisan_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(50), nullable=False)  # e.g., 'bank_transfer', 'paypal'
    account_details = db.Column(db.Text)  # JSON string with account info
    status = db.Column(db.String(20), default='pending')  # pending, completed, rejected
    requested_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    processed_at = db.Column(db.DateTime(timezone=True))
    
    # Relationship with explicit foreign_key
    artisan = db.relationship('User', foreign_keys=[artisan_id], backref='artisan_withdrawals', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'artisan_id': self.artisan_id,
            'amount': self.amount,
            'method': self.method,
            'status': self.status,
            'requested_at': self.requested_at.isoformat() if self.requested_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None
        }
        
class Review(db.Model):
    """
    Docstring for Review
    """
    __tablename__ = 'reviews'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    service_request_id = db.Column(db.String(36), db.ForeignKey('service_requests.id'), nullable=False)
    reviewer_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    reviewee_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    # Relationships with explicit foreign_keys
    service_request = db.relationship('ServiceRequest', foreign_keys=[service_request_id], backref='request_reviews', lazy=True)
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref='given_reviews', lazy=True)
    reviewee = db.relationship('User', foreign_keys=[reviewee_id], backref='received_reviews', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'service_request_id': self.service_request_id,
            'reviewer_id': self.reviewer_id,
            'reviewee_id': self.reviewee_id,
            'rating': self.rating,
            'comments': self.comments,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
# Update Payment model with unique backref name

class Payment(db.Model):
    """Payment Model for service requests"""
    __tablename__ = 'payments'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    service_request_id = db.Column(db.String(36), db.ForeignKey('service_requests.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    
    # Payment details
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), default='NGN')
    payment_method = db.Column(db.String(50), nullable=False)
    payment_status = db.Column(db.String(20), default='pending')
    payment_type = db.Column(db.String(20), default='service_fee')
    
    # Company bank details
    company_account_name = db.Column(db.String(100))
    company_account_number = db.Column(db.String(20))
    company_bank_name = db.Column(db.String(100))
    
    # User payment details
    payer_account_name = db.Column(db.String(100))
    payer_account_number = db.Column(db.String(20))
    payer_bank_name = db.Column(db.String(100))
    
    # Receipt information
    receipt_number = db.Column(db.String(50), unique=True)
    receipt_image = db.Column(db.String(255))
    transaction_reference = db.Column(db.String(100))
    
    # Dates
    payment_date = db.Column(db.DateTime(timezone=True))
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    
    # Notes
    admin_notes = db.Column(db.Text)
    payment_notes = db.Column(db.Text)
    
    # Metadata
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # FIXED: Changed backref name to be unique
    service_request = db.relationship('ServiceRequest', backref='request_payments_master', lazy=True)
    user = db.relationship('User', foreign_keys=[user_id], backref='user_payments_master', lazy=True)
    verifier = db.relationship('User', foreign_keys=[verified_by], backref='verified_payments_master', lazy=True)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
    
    def generate_receipt_number(self):
        """Generate unique receipt number"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = str(uuid.uuid4().int)[:6]
        return f'REC-{timestamp}-{random_part}'
    
    def to_dict(self):
        return {
            'id': self.id,
            'service_request_id': self.service_request_id,
            'receipt_number': self.receipt_number,
            'amount': self.amount,
            'currency': self.currency,
            'payment_method': self.payment_method,
            'payment_status': self.payment_status,
            'payment_type': self.payment_type,
            'company_account_details': {
                'account_name': self.company_account_name,
                'account_number': self.company_account_number,
                'bank_name': self.company_bank_name
            } if self.company_account_name else None,
            'payer_details': {
                'account_name': self.payer_account_name,
                'account_number': self.payer_account_number,
                'bank_name': self.payer_bank_name
            } if self.payer_account_name else None,
            'receipt_image': self.receipt_image,
            'transaction_reference': self.transaction_reference,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'payment_notes': self.payment_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'verified': self.verified_at is not None
        }

# Update PaymentTransaction model with unique backref name

class PaymentTransaction(db.Model):
    """
    Docstring for PaymentTransaction
    """
    __tablename__ = 'payment_transactions'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    service_request_id = db.Column(db.String(36), db.ForeignKey('service_requests.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_status = db.Column(db.String(20), default='pending')
    transaction_reference = db.Column(db.String(100), unique=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    # FIXED: Changed backref names to be unique
    user = db.relationship('User', foreign_keys=[user_id], backref='user_transactions', lazy=True)
    service_request = db.relationship('ServiceRequest', foreign_keys=[service_request_id], backref='request_transactions', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'service_request_id': self.service_request_id,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'transaction_status': self.transaction_status,
            'transaction_reference': self.transaction_reference,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    

