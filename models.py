from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import json

db = SQLAlchemy()

def generate_uuid():
    return str(uuid.uuid4())

class User(UserMixin, db.Model):
    """Client/Service Seeker Model"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    service_requests = db.relationship('ServiceRequest', backref='client', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'phone': self.phone,
            'full_name': self.full_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Artisan(UserMixin, db.Model):
    """Artisan/Service Provider Model"""
    __tablename__ = 'artisans'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Plumbing, Electrical, etc.
    skills = db.Column(db.Text)
    credentials = db.Column(db.Text)  # JSON string of certifications
    experience_years = db.Column(db.Integer, default=0)
    availability = db.Column(db.String(20), default='available')  # available, busy, offline
    is_verified = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    rating = db.Column(db.Float, default=0.0)
    portfolio_images = db.Column(db.Text)  # JSON array of image paths
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    assigned_services = db.relationship('ServiceRequest', backref='assigned_artisan', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'phone': self.phone,
            'full_name': self.full_name,
            'category': self.category,
            'skills': self.skills,
            'experience_years': self.experience_years,
            'availability': self.availability,
            'rating': self.rating,
            'is_verified': self.is_verified
        }

class Admin(UserMixin, db.Model):
    """Administrator Model"""
    __tablename__ = 'admins'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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
            'icon': self.icon
        }

class ServiceRequest(db.Model):
    """Service Request Model"""
    __tablename__ = 'service_requests'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    artisan_id = db.Column(db.String(36), db.ForeignKey('artisans.id'), nullable=True)
    category_id = db.Column(db.String(36), db.ForeignKey('service_categories.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    preferred_date = db.Column(db.Date)
    preferred_time = db.Column(db.String(50))
    status = db.Column(db.String(20), default='pending')  # pending, assigned, in_progress, completed, cancelled
    admin_notes = db.Column(db.Text)
    price_estimate = db.Column(db.Float)
    actual_price = db.Column(db.Float)
    rating = db.Column(db.Integer)  # 1-5
    feedback = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    category = db.relationship('ServiceCategory', backref='service_requests', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'location': self.location,
            'preferred_date': self.preferred_date.isoformat() if self.preferred_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'category': self.category.name if self.category else None,
            'artisan_name': self.assigned_artisan.full_name if self.assigned_artisan else None,
            'client_name': self.client.full_name if self.client else None
        }

class Notification(db.Model):
    """Notification System Model"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), nullable=False)  # Can be user, artisan, or admin ID
    user_type = db.Column(db.String(20), nullable=False)  # user, artisan, admin
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(50))  # job_assigned, status_update, etc.
    related_id = db.Column(db.String(36))  # ID of related entity (service request, etc.)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'notification_type': self.notification_type
        }

class AccountDeactivation(db.Model):
    """Track account deactivations"""
    __tablename__ = 'account_deactivations'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'user', 'artisan', 'admin'
    reason = db.Column(db.Text)
    deactivated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    reactivated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_permanent = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'reason': self.reason,
            'deactivated_at': self.deactivated_at.isoformat() if self.deactivated_at else None,
            'reactivated_at': self.reactivated_at.isoformat() if self.reactivated_at else None,
            'is_permanent': self.is_permanent
        }


class VerificationRequest(db.Model):
    """Track verification requests"""
    __tablename__ = 'verification_requests'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'artisan', 'user', 'admin'
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    request_data = db.Column(db.Text)  # JSON string with verification data
    admin_notes = db.Column(db.Text)
    reviewed_by = db.Column(db.String(36), db.ForeignKey('admins.id'))
    reviewed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    reviewer = db.relationship('Admin', backref='verification_requests', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'status': self.status,
            'request_data': json.loads(self.request_data) if self.request_data else None,
            'admin_notes': self.admin_notes,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Withdrawal(db.Model):
    """Track earnings withdrawals"""
    __tablename__ = 'withdrawals'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    artisan_id = db.Column(db.String(36), db.ForeignKey('artisans.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    fee = db.Column(db.Float, default=0.0)
    net_amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # bank, mobile_money, etc.
    account_details = db.Column(db.Text)  # JSON string with account info
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    reference_number = db.Column(db.String(100), unique=True)
    admin_notes = db.Column(db.Text)
    processed_by = db.Column(db.String(36), db.ForeignKey('admins.id'))
    processed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    # Relationships
    artisan = db.relationship('Artisan', backref='withdrawals', lazy=True)
    processor = db.relationship('Admin', backref='processed_withdrawals', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'artisan_id': self.artisan_id,
            'amount': self.amount,
            'fee': self.fee,
            'net_amount': self.net_amount,
            'payment_method': self.payment_method,
            'account_details': json.loads(self.account_details) if self.account_details else None,
            'status': self.status,
            'reference_number': self.reference_number,
            'admin_notes': self.admin_notes,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class UserSettings(db.Model):
    """Store user preferences and settings"""
    __tablename__ = 'user_settings'
    
    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String(36), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'user', 'artisan', 'admin'
    settings_type = db.Column(db.String(50), nullable=False)  # 'notifications', 'privacy', 'appearance'
    settings_data = db.Column(db.Text)  # JSON string with settings
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_type': self.user_type,
            'settings_type': self.settings_type,
            'settings_data': json.loads(self.settings_data) if self.settings_data else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
