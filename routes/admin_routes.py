from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from functools import wraps
from models import db, Admin, User, Artisan, ServiceRequest, ServiceCategory, Notification
from datetime import datetime, timedelta
import json

admin_bp = Blueprint('admin_bp', __name__)

# Admin Authentication Middleware
def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not isinstance(current_user, Admin):
            if request.is_json:
                return jsonify({'error': 'Admin access required'}), 403
            else:
                return render_template('error.html', message='Admin access required'), 403
        return f(*args, **kwargs)
    return decorated

# Dashboard Routes
@admin_bp.route('/dashboard')
@admin_required
def admin_dashboard():
    # Get statistics
    total_users = User.query.count()
    total_artisans = Artisan.query.count()
    total_requests = ServiceRequest.query.count()
    pending_requests = ServiceRequest.query.filter_by(status='pending').count()
    active_requests = ServiceRequest.query.filter_by(status='in_progress').count()
    completed_requests = ServiceRequest.query.filter_by(status='completed').count()
    pending_verifications = Artisan.query.filter_by(is_verified=False).count()
    
    # Recent requests
    recent_requests = ServiceRequest.query\
        .order_by(ServiceRequest.created_at.desc())\
        .limit(10)\
        .all()
    
    # Pending verifications
    pending_artisans = Artisan.query.filter_by(is_verified=False)\
        .order_by(Artisan.created_at.desc())\
        .limit(5)\
        .all()
    
    if request.is_json:
        return jsonify({
            'stats': {
                'total_users': total_users,
                'total_artisans': total_artisans,
                'total_requests': total_requests,
                'pending_requests': pending_requests,
                'active_requests': active_requests,
                'completed_requests': completed_requests,
                'pending_verifications': pending_verifications
            },
            'recent_requests': [req.to_dict() for req in recent_requests]
        })
    else:
        return render_template('admin/dashboard.html',
                              stats={
                                  'total_users': total_users,
                                  'total_artisans': total_artisans,
                                  'total_requests': total_requests,
                                  'pending_requests': pending_requests,
                                  'active_requests': active_requests,
                                  'completed_requests': completed_requests,
                                  'pending_verifications': pending_verifications
                              },
                              recent_requests=recent_requests,
                              pending_verifications=pending_artisans)

# User Management
@admin_bp.route('/users', methods=['GET'])
@admin_required
def manage_users():
    users = User.query.all()
    
    if request.is_json:
        return jsonify({'users': [user.to_dict() for user in users]})
    else:
        return render_template('admin/manage_users.html', users=users)

@admin_bp.route('/users/<user_id>', methods=['GET', 'PUT', 'DELETE'])
@admin_required
def manage_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'GET':
        if request.is_json:
            return jsonify(user.to_dict())
        else:
            return render_template('admin/view_user.html', user=user)
    
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
def manage_artisans():
    artisans = Artisan.query.all()
    
    if request.is_json:
        return jsonify({'artisans': [artisan.to_dict() for artisan in artisans]})
    else:
        return render_template('admin/manage_artisans.html', artisans=artisans)

@admin_bp.route('/artisans/pending-verification', methods=['GET'])
@admin_required
def get_pending_verification():
    artisans = Artisan.query.filter_by(is_verified=False).all()
    
    if request.is_json:
        return jsonify({'artisans': [artisan.to_dict() for artisan in artisans]})
    else:
        return render_template('admin/verify_artisans.html', artisans=artisans)

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
        if request.is_json:
            return jsonify(artisan.to_dict())
        else:
            return render_template('admin/view_artisan.html', artisan=artisan)
    
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
def manage_requests():
    status = request.args.get('status')
    
    query = ServiceRequest.query
    
    if status:
        query = query.filter_by(status=status)
    
    service_requests = query.order_by(ServiceRequest.created_at.desc()).all()
    
    if request.is_json:
        return jsonify({'service_requests': [req.to_dict() for req in service_requests]})
    else:
        return render_template('admin/manage_requests.html', 
                              requests=service_requests,
                              status_filter=status)

@admin_bp.route('/service-requests/<request_id>', methods=['GET'])
@admin_required
def view_request_admin(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    # Get available artisans for this category
    available_artisans = Artisan.query.filter_by(
        category=service_request.category.name,
        is_verified=True,
        is_active=True
    ).all()
    
    if request.is_json:
        return jsonify({
            'request': service_request.to_dict(),
            'available_artisans': [artisan.to_dict() for artisan in available_artisans]
        })
    else:
        return render_template('admin/view_request.html', 
                              request=service_request,
                              available_artisans=available_artisans)

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
        
        if request.is_json:
            return jsonify({'categories': [cat.to_dict() for cat in categories]})
        else:
            return render_template('admin/manage_categories.html', categories=categories)
    
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
    
    if request.is_json:
        return jsonify({'notifications': [n.to_dict() for n in notifications]})
    else:
        return render_template('admin/notifications.html', notifications=notifications)

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
    
    if request.is_json:
        return jsonify(report_data)
    else:
        return render_template('admin/reports.html', report_data=report_data)