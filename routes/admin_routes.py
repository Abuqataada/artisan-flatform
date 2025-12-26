from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from ..models import db, Admin, User, Artisan, ServiceRequest, ServiceCategory, Notification
from datetime import datetime
import json

admin_bp = Blueprint('admin_routes', __name__)

# Admin Authentication Middleware
def admin_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not isinstance(current_user, Admin):
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Dashboard Routes
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    # Get statistics
    total_users = User.query.count()
    total_artisans = Artisan.query.count()
    total_requests = ServiceRequest.query.count()
    pending_requests = ServiceRequest.query.filter_by(status='pending').count()
    active_requests = ServiceRequest.query.filter_by(status='in_progress').count()
    
    # Recent requests
    recent_requests = ServiceRequest.query\
        .order_by(ServiceRequest.created_at.desc())\
        .limit(10)\
        .all()
    
    return jsonify({
        'stats': {
            'total_users': total_users,
            'total_artisans': total_artisans,
            'total_requests': total_requests,
            'pending_requests': pending_requests,
            'active_requests': active_requests
        },
        'recent_requests': [req.to_dict() for req in recent_requests]
    })

# User Management
@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_users():
    users = User.query.all()
    return jsonify({'users': [user.to_dict() for user in users]})

@admin_bp.route('/users/<user_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def manage_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'GET':
        return jsonify(user.to_dict())
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'is_verified' in data:
            user.is_verified = data['is_verified']
        
        db.session.commit()
        return jsonify({'message': 'User updated successfully'})
    
    elif request.method == 'DELETE':
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'User deleted successfully'})

# Artisan Management
@admin_bp.route('/artisans', methods=['GET'])
@admin_required
def get_artisans():
    artisans = Artisan.query.all()
    return jsonify({'artisans': [artisan.to_dict() for artisan in artisans]})

@admin_bp.route('/artisans/pending-verification', methods=['GET'])
@admin_required
def get_pending_verification():
    artisans = Artisan.query.filter_by(is_verified=False).all()
    return jsonify({'artisans': [artisan.to_dict() for artisan in artisans]})

@admin_bp.route('/artisans/<artisan_id>/verify', methods=['PUT'])
@admin_required
def verify_artisan(artisan_id):
    artisan = Artisan.query.get_or_404(artisan_id)
    
    data = request.get_json()
    artisan.is_verified = data.get('verified', True)
    
    # Create notification for artisan
    notification = Notification(
        user_id=artisan.id,
        user_type='artisan',
        title='Account Verified',
        message='Your artisan account has been verified by admin.',
        notification_type='account_verified'
    )
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({'message': 'Artisan verification status updated'})

@admin_bp.route('/artisans/<artisan_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def manage_artisan(artisan_id):
    artisan = Artisan.query.get_or_404(artisan_id)
    
    if request.method == 'GET':
        return jsonify(artisan.to_dict())
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        # Update editable fields
        editable_fields = ['full_name', 'phone', 'category', 'skills', 
                          'experience_years', 'availability', 'is_active']
        
        for field in editable_fields:
            if field in data:
                setattr(artisan, field, data[field])
        
        db.session.commit()
        return jsonify({'message': 'Artisan updated successfully'})
    
    elif request.method == 'DELETE':
        db.session.delete(artisan)
        db.session.commit()
        return jsonify({'message': 'Artisan deleted successfully'})

# Service Request Management
@admin_bp.route('/service-requests', methods=['GET'])
@admin_required
def get_all_service_requests():
    status = request.args.get('status')
    
    query = ServiceRequest.query
    
    if status:
        query = query.filter_by(status=status)
    
    service_requests = query.order_by(ServiceRequest.created_at.desc()).all()
    return jsonify({'service_requests': [req.to_dict() for req in service_requests]})

@admin_bp.route('/service-requests/<request_id>', methods=['GET'])
@admin_required
def get_service_request_details(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    return jsonify(service_request.to_dict())

@admin_bp.route('/service-requests/<request_id>/assign', methods=['POST'])
@admin_required
def assign_artisan(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    if service_request.status != 'pending':
        return jsonify({'error': 'Only pending requests can be assigned'}), 400
    
    data = request.get_json()
    artisan_id = data['artisan_id']
    
    artisan = Artisan.query.get_or_404(artisan_id)
    
    # Check artisan availability
    if artisan.availability != 'available':
        return jsonify({'error': 'Artisan is not available'}), 400
    
    # Assign artisan
    service_request.artisan_id = artisan_id
    service_request.status = 'assigned'
    service_request.admin_notes = data.get('admin_notes', '')
    
    # Update artisan availability
    artisan.availability = 'busy'
    
    # Create notifications
    # For artisan
    artisan_notification = Notification(
        user_id=artisan_id,
        user_type='artisan',
        title='New Job Assigned',
        message=f'You have been assigned a new job: {service_request.title}',
        notification_type='job_assigned',
        related_id=request_id
    )
    
    # For user
    user_notification = Notification(
        user_id=service_request.user_id,
        user_type='user',
        title='Artisan Assigned',
        message=f'An artisan has been assigned to your service request: {service_request.title}',
        notification_type='artisan_assigned',
        related_id=request_id
    )
    
    db.session.add(artisan_notification)
    db.session.add(user_notification)
    db.session.commit()
    
    return jsonify({'message': 'Artisan assigned successfully'})

@admin_bp.route('/service-requests/<request_id>/status', methods=['PUT'])
@admin_required
def update_request_status(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    data = request.get_json()
    new_status = data['status']
    
    # Validate status transition
    valid_transitions = {
        'pending': ['assigned', 'cancelled'],
        'assigned': ['in_progress', 'cancelled'],
        'in_progress': ['completed', 'cancelled'],
        'completed': [],
        'cancelled': []
    }
    
    if new_status not in valid_transitions.get(service_request.status, []):
        return jsonify({'error': 'Invalid status transition'}), 400
    
    service_request.status = new_status
    
    # Update artisan availability if job is completed or cancelled
    if new_status in ['completed', 'cancelled'] and service_request.artisan_id:
        artisan = service_request.assigned_artisan
        artisan.availability = 'available'
    
    # Create notification for user
    notification = Notification(
        user_id=service_request.user_id,
        user_type='user',
        title='Service Status Updated',
        message=f'Your service request status has been updated to: {new_status}',
        notification_type='status_update',
        related_id=request_id
    )
    
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({'message': 'Status updated successfully'})

@admin_bp.route('/service-requests/<request_id>/price', methods=['PUT'])
@admin_required
def update_request_price(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    data = request.get_json()
    
    if 'price_estimate' in data:
        service_request.price_estimate = data['price_estimate']
    
    if 'actual_price' in data:
        service_request.actual_price = data['actual_price']
    
    db.session.commit()
    return jsonify({'message': 'Price updated successfully'})

# Category Management
@admin_bp.route('/categories', methods=['GET', 'POST'])
@admin_required
def manage_categories():
    if request.method == 'GET':
        categories = ServiceCategory.query.all()
        return jsonify({'categories': [cat.to_dict() for cat in categories]})
    
    elif request.method == 'POST':
        data = request.get_json()
        
        category = ServiceCategory(
            name=data['name'],
            description=data.get('description', ''),
            icon=data.get('icon', 'default')
        )
        
        db.session.add(category)
        db.session.commit()
        
        return jsonify({
            'message': 'Category created successfully',
            'category': category.to_dict()
        }), 201

@admin_bp.route('/categories/<category_id>', methods=['PUT', 'DELETE'])
@admin_required
def manage_category(category_id):
    category = ServiceCategory.query.get_or_404(category_id)
    
    if request.method == 'PUT':
        data = request.get_json()
        
        if 'name' in data:
            category.name = data['name']
        
        if 'description' in data:
            category.description = data['description']
        
        if 'icon' in data:
            category.icon = data['icon']
        
        if 'is_active' in data:
            category.is_active = data['is_active']
        
        db.session.commit()
        return jsonify({'message': 'Category updated successfully'})
    
    elif request.method == 'DELETE':
        db.session.delete(category)
        db.session.commit()
        return jsonify({'message': 'Category deleted successfully'})

# Notification System
@admin_bp.route('/notifications', methods=['GET'])
@admin_required
def get_admin_notifications():
    notifications = Notification.query.filter_by(
        user_type='admin'
    ).order_by(Notification.created_at.desc()).limit(50).all()
    
    return jsonify({'notifications': [n.to_dict() for n in notifications]})

# Report Generation
@admin_bp.route('/reports/service-requests', methods=['GET'])
@admin_required
def generate_service_report():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = ServiceRequest.query
    
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(ServiceRequest.created_at >= start)
    
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d')
        query = query.filter(ServiceRequest.created_at <= end)
    
    requests = query.all()
    
    # Generate report data
    report_data = {
        'total_requests': len(requests),
        'by_status': {},
        'by_category': {},
        'revenue': {
            'estimated': sum(r.price_estimate or 0 for r in requests),
            'actual': sum(r.actual_price or 0 for r in requests)
        }
    }
    
    for req in requests:
        # Count by status
        report_data['by_status'][req.status] = report_data['by_status'].get(req.status, 0) + 1
        
        # Count by category
        category_name = req.category.name if req.category else 'Unknown'
        report_data['by_category'][category_name] = report_data['by_category'].get(category_name, 0) + 1
    
    return jsonify(report_data)