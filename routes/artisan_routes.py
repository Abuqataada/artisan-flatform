from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user
from ..models import db, Artisan, ServiceRequest, ServiceCategory, Notification
from datetime import datetime
import json

artisan_bp = Blueprint('artisan_routes', __name__)

# Artisan Authentication Middleware
def artisan_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not isinstance(current_user, Artisan):
            return jsonify({'error': 'Artisan access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# Registration and Profile
@artisan_bp.route('/register', methods=['POST'])
def register():
    data = request.form if request.form else request.get_json()
    
    # Check if artisan already exists
    if Artisan.query.filter_by(email=data.get('email')).first():
        return jsonify({'error': 'Email already registered'}), 400
    
    # Create new artisan
    artisan = Artisan(
        email=data['email'],
        phone=data['phone'],
        full_name=data['full_name'],
        category=data['category'],
        skills=data.get('skills', ''),
        experience_years=data.get('experience_years', 0),
        availability='available',
        is_verified=False  # Requires admin verification
    )
    artisan.set_password(data['password'])
    
    # Handle credentials (JSON array)
    if 'credentials' in data:
        artisan.credentials = json.dumps(data['credentials'])
    
    # Handle portfolio images
    if 'portfolio_images' in data:
        artisan.portfolio_images = json.dumps(data['portfolio_images'])
    
    db.session.add(artisan)
    db.session.commit()
    
    # Create notification for admin
    notification = Notification(
        user_id='admin',
        user_type='admin',
        title='New Artisan Registration',
        message=f'New artisan registered: {artisan.full_name} ({artisan.category})',
        notification_type='new_artisan',
        related_id=artisan.id
    )
    db.session.add(notification)
    
    # Create welcome notification for artisan
    artisan_notification = Notification(
        user_id=artisan.id,
        user_type='artisan',
        title='Registration Successful',
        message='Your registration is pending admin verification.',
        notification_type='registration_pending'
    )
    db.session.add(artisan_notification)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Registration submitted for verification',
        'artisan': artisan.to_dict()
    }), 201

@artisan_bp.route('/profile', methods=['GET', 'PUT'])
@artisan_required
def profile():
    if request.method == 'GET':
        artisan_data = current_user.to_dict()
        
        # Add additional fields
        artisan_data['credentials'] = json.loads(current_user.credentials) if current_user.credentials else []
        artisan_data['portfolio_images'] = json.loads(current_user.portfolio_images) if current_user.portfolio_images else []
        
        return jsonify(artisan_data)
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        # Update editable fields
        editable_fields = ['phone', 'full_name', 'category', 'skills', 
                          'experience_years', 'availability']
        
        for field in editable_fields:
            if field in data:
                setattr(current_user, field, data[field])
        
        # Handle credentials update
        if 'credentials' in data:
            current_user.credentials = json.dumps(data['credentials'])
        
        # Handle portfolio images update
        if 'portfolio_images' in data:
            current_user.portfolio_images = json.dumps(data['portfolio_images'])
        
        db.session.commit()
        return jsonify({
            'message': 'Profile updated successfully',
            'artisan': current_user.to_dict()
        })

# Job Management
@artisan_bp.route('/assigned-jobs', methods=['GET'])
@artisan_required
def get_assigned_jobs():
    status = request.args.get('status', 'assigned')
    
    jobs = ServiceRequest.query.filter_by(
        artisan_id=current_user.id,
        status=status
    ).order_by(ServiceRequest.created_at.desc()).all()
    
    return jsonify({'jobs': [job.to_dict() for job in jobs]})

@artisan_bp.route('/job/<job_id>', methods=['GET'])
@artisan_required
def get_job_details(job_id):
    job = ServiceRequest.query.get_or_404(job_id)
    
    # Ensure artisan is assigned to this job
    if job.artisan_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify(job.to_dict())

@artisan_bp.route('/job/<job_id>/accept', methods=['PUT'])
@artisan_required
def accept_job(job_id):
    job = ServiceRequest.query.get_or_404(job_id)
    
    if job.artisan_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if job.status != 'assigned':
        return jsonify({'error': 'Job is not in assigned status'}), 400
    
    job.status = 'in_progress'
    current_user.availability = 'busy'
    
    # Create notification for admin
    notification = Notification(
        user_id='admin',
        user_type='admin',
        title='Job Accepted by Artisan',
        message=f'Artisan {current_user.full_name} has accepted job: {job.title}',
        notification_type='job_accepted',
        related_id=job_id
    )
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({'message': 'Job accepted successfully'})

@artisan_bp.route('/job/<job_id>/complete', methods=['PUT'])
@artisan_required
def complete_job(job_id):
    job = ServiceRequest.query.get_or_404(job_id)
    
    if job.artisan_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if job.status != 'in_progress':
        return jsonify({'error': 'Job is not in progress'}), 400
    
    job.status = 'completed'
    current_user.availability = 'available'
    
    # Create notification for admin
    admin_notification = Notification(
        user_id='admin',
        user_type='admin',
        title='Job Completed',
        message=f'Job {job.title} has been completed by {current_user.full_name}',
        notification_type='job_completed',
        related_id=job_id
    )
    
    # Create notification for user
    user_notification = Notification(
        user_id=job.user_id,
        user_type='user',
        title='Service Completed',
        message=f'Your service request has been completed by {current_user.full_name}',
        notification_type='service_completed',
        related_id=job_id
    )
    
    db.session.add(admin_notification)
    db.session.add(user_notification)
    db.session.commit()
    
    return jsonify({'message': 'Job marked as completed'})

@artisan_bp.route('/job/<job_id>/report-issue', methods=['POST'])
@artisan_required
def report_job_issue(job_id):
    job = ServiceRequest.query.get_or_404(job_id)
    
    if job.artisan_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    issue_description = data.get('issue_description', '')
    
    # Update admin notes
    if job.admin_notes:
        job.admin_notes += f"\n\n[Issue Reported by Artisan]: {issue_description}"
    else:
        job.admin_notes = f"[Issue Reported by Artisan]: {issue_description}"
    
    # Create notification for admin
    notification = Notification(
        user_id='admin',
        user_type='admin',
        title='Issue Reported on Job',
        message=f'Artisan {current_user.full_name} reported an issue on job: {job.title}',
        notification_type='job_issue',
        related_id=job_id
    )
    db.session.add(notification)
    db.session.commit()
    
    return jsonify({'message': 'Issue reported successfully'})

# Availability Management
@artisan_bp.route('/availability', methods=['PUT'])
@artisan_required
def update_availability():
    data = request.get_json()
    
    valid_statuses = ['available', 'busy', 'offline']
    new_status = data.get('status')
    
    if new_status not in valid_statuses:
        return jsonify({'error': 'Invalid availability status'}), 400
    
    current_user.availability = new_status
    db.session.commit()
    
    return jsonify({
        'message': 'Availability updated successfully',
        'availability': new_status
    })

# Earnings/Performance
@artisan_bp.route('/earnings', methods=['GET'])
@artisan_required
def get_earnings():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    query = ServiceRequest.query.filter_by(
        artisan_id=current_user.id,
        status='completed'
    )
    
    if start_date:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        query = query.filter(ServiceRequest.created_at >= start)
    
    if end_date:
        end = datetime.strptime(end_date, '%Y-%m-%d')
        query = query.filter(ServiceRequest.created_at <= end)
    
    completed_jobs = query.all()
    
    total_earnings = sum(job.actual_price or 0 for job in completed_jobs)
    total_jobs = len(completed_jobs)
    average_rating = current_user.rating
    
    return jsonify({
        'total_earnings': total_earnings,
        'total_jobs': total_jobs,
        'average_rating': average_rating,
        'jobs': [job.to_dict() for job in completed_jobs]
    })

# Notifications
@artisan_bp.route('/notifications', methods=['GET'])
@artisan_required
def get_artisan_notifications():
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        user_type='artisan'
    ).order_by(Notification.created_at.desc()).all()
    
    return jsonify({'notifications': [n.to_dict() for n in notifications]})

@artisan_bp.route('/notifications/<notification_id>/read', methods=['PUT'])
@artisan_required
def mark_artisan_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'message': 'Notification marked as read'})

# Service Categories
@artisan_bp.route('/categories', methods=['GET'])
def get_service_categories():
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    return jsonify({'categories': [cat.to_dict() for cat in categories]})