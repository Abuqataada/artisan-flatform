from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from ..models import db, User, ServiceRequest, ServiceCategory, Notification
from datetime import datetime
import json

user_bp = Blueprint('user_routes', __name__)

# Authentication Routes
@user_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form if request.form else request.get_json()
        
        # Check if user already exists
        if User.query.filter_by(email=data.get('email')).first():
            return jsonify({'error': 'Email already registered'}), 400
        
        # Create new user
        user = User(
            email=data['email'],
            phone=data['phone'],
            full_name=data['full_name'],
            address=data.get('address', '')
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Create welcome notification
        notification = Notification(
            user_id=user.id,
            user_type='user',
            title='Welcome to Uwaila Global!',
            message='Your account has been created successfully.',
            notification_type='welcome'
        )
        db.session.add(notification)
        db.session.commit()
        
        return jsonify({
            'message': 'Registration successful',
            'user': user.to_dict()
        }), 201
    
    return render_template('user/register.html')

@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.form if request.form else request.get_json()
        
        user = User.query.filter_by(email=data['email']).first()
        
        if not user or not user.check_password(data['password']):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 403
        
        login_user(user)
        return jsonify({
            'message': 'Login successful',
            'user': user.to_dict()
        }), 200
    
    return render_template('user/login.html')

@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200

# Service Request Routes
@user_bp.route('/dashboard')
@login_required
def dashboard():
    user_requests = ServiceRequest.query.filter_by(user_id=current_user.id)\
        .order_by(ServiceRequest.created_at.desc()).all()
    
    return jsonify({
        'user': current_user.to_dict(),
        'service_requests': [req.to_dict() for req in user_requests]
    })

@user_bp.route('/service-request', methods=['POST'])
@login_required
def create_service_request():
    data = request.form if request.form else request.get_json()
    
    service_request = ServiceRequest(
        user_id=current_user.id,
        category_id=data['category_id'],
        title=data['title'],
        description=data['description'],
        location=data['location'],
        preferred_date=datetime.strptime(data['preferred_date'], '%Y-%m-%d') if data.get('preferred_date') else None,
        preferred_time=data.get('preferred_time'),
        status='pending'
    )
    
    db.session.add(service_request)
    db.session.commit()
    
    # Create notification for admin
    notification = Notification(
        user_id='admin',  # Will be handled by admin notification system
        user_type='admin',
        title='New Service Request',
        message=f'New service request from {current_user.full_name}: {service_request.title}',
        notification_type='new_request',
        related_id=service_request.id
    )
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({
        'message': 'Service request submitted successfully',
        'request': service_request.to_dict()
    }), 201

@user_bp.route('/service-request/<request_id>', methods=['GET'])
@login_required
def get_service_request(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    # Ensure user owns this request
    if service_request.user_id != current_user.id and not isinstance(current_user, Admin):
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify(service_request.to_dict())

@user_bp.route('/service-request/<request_id>/status')
@login_required
def get_request_status(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    if service_request.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'status': service_request.status,
        'artisan_assigned': service_request.artisan_id is not None,
        'artisan_name': service_request.assigned_artisan.full_name if service_request.assigned_artisan else None
    })

@user_bp.route('/service-request/<request_id>/feedback', methods=['POST'])
@login_required
def submit_feedback(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    if service_request.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if service_request.status != 'completed':
        return jsonify({'error': 'Service must be completed to submit feedback'}), 400
    
    data = request.get_json()
    service_request.rating = data['rating']
    service_request.feedback = data.get('feedback', '')
    
    # Update artisan rating
    if service_request.artisan_id and data['rating']:
        artisan = service_request.assigned_artisan
        # Calculate new average rating
        completed_services = ServiceRequest.query.filter_by(
            artisan_id=artisan.id,
            status='completed'
        ).filter(ServiceRequest.rating.isnot(None)).all()
        
        if completed_services:
            total_rating = sum(s.rating for s in completed_services)
            artisan.rating = total_rating / len(completed_services)
    
    db.session.commit()
    
    return jsonify({'message': 'Feedback submitted successfully'})

# Category Routes
@user_bp.route('/categories', methods=['GET'])
def get_categories():
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    return jsonify({'categories': [cat.to_dict() for cat in categories]})

# Notification Routes
@user_bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        user_type='user'
    ).order_by(Notification.created_at.desc()).all()
    
    return jsonify({'notifications': [n.to_dict() for n in notifications]})

@user_bp.route('/notifications/<notification_id>/read', methods=['PUT'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'message': 'Notification marked as read'})

# Profile Management
@user_bp.route('/profile', methods=['GET', 'PUT'])
@login_required
def profile():
    if request.method == 'GET':
        return jsonify(current_user.to_dict())
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        if 'email' in data and data['email'] != current_user.email:
            # Check if email is already taken
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email already registered'}), 400
            current_user.email = data['email']
        
        if 'phone' in data:
            current_user.phone = data['phone']
        
        if 'full_name' in data:
            current_user.full_name = data['full_name']
        
        if 'address' in data:
            current_user.address = data['address']
        
        db.session.commit()
        return jsonify({
            'message': 'Profile updated successfully',
            'user': current_user.to_dict()
        })