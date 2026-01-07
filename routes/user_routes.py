# user_routes.py

from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app
import os
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import db, User, ServiceRequest, ServiceCategory, Notification, ArtisanProfile
from datetime import datetime
import json
from forms import LoginForm, UserRegistrationForm

user_bp = Blueprint('user_bp', __name__)

def get_user_stats(user_id):
    """Get user statistics for dashboard"""
    total_requests = ServiceRequest.query.filter_by(user_id=user_id).count()
    pending_requests = ServiceRequest.query.filter_by(user_id=user_id, status='pending').count()
    in_progress_requests = ServiceRequest.query.filter_by(user_id=user_id, status='in_progress').count()
    completed_requests = ServiceRequest.query.filter_by(user_id=user_id, status='completed').count()
    
    return {
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'in_progress_requests': in_progress_requests,
        'completed_requests': completed_requests
    }
    
# Authentication Routes - CUSTOMER REGISTRATION
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
            address=data.get('address', ''),
            user_type='customer'  # CRITICAL: Set user_type
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        # Create welcome notification
        notification = Notification(
            user_id=user.id,
            title='Welcome to Uwaila Global!',
            message='Your account has been created successfully.',
            notification_type='welcome'
        )
        db.session.add(notification)
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'message': 'Registration successful',
                'user': user.to_dict()
            }), 201
        else:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('user_bp.login'))
    
    return render_template('auth/user_register.html')
       
@user_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        # Redirect based on user type
        if current_user.user_type == 'admin':
            return redirect(url_for('admin_bp.admin_dashboard'))
        if current_user.user_type == 'artisan':
            return redirect(url_for('artisan_bp.artisan_dashboard'))
        else:
            return redirect(url_for('user_bp.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        # Try to find user
        user = User.query.filter_by(email=form.email.data).first()
        if not user:
            # Try artisan
            user = User.query.filter_by(email=form.email.data, user_type='artisan').first()
            if not user:
                # Try admin
                user = User.query.filter_by(email=form.email.data, user_type='admin').first()
        
        if user and user.check_password(form.password.data):
            if not getattr(user, 'is_active', True):
                flash('Account is deactivated', 'danger')
                return redirect(url_for('user_bp.login'))
            
            login_user(user, remember=form.remember.data)
            
            # Redirect based on user type
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            if user.user_type == 'admin':
                flash('Welcome back, Admin!', 'success')
                return redirect(url_for('admin_bp.admin_dashboard'))
            if user.user_type == 'artisan':
                flash('Welcome back, Artisan!', 'success')
                return redirect(url_for('artisan_bp.artisan_dashboard'))
            else:
                flash('Welcome back!', 'success')
                return redirect(url_for('user_bp.dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('auth/login.html', form=form)

@user_bp.route('/logout')
@login_required
def logout():
    logout_user()
    if request.is_json:
        return jsonify({'message': 'Logged out successfully'}), 200
    else:
        flash('Logged out successfully', 'success')
        return redirect(url_for('user_bp.login'))

@user_bp.route('/upgrade-to-artisan', methods=['GET', 'POST'])
@login_required
def upgrade_to_artisan():
    """Allow existing customers to become artisans"""
    # Get the logged-in user
    user = current_user
    
    # Check if user is already an artisan
    if user.is_artisan:
        flash('You are already registered as an artisan!', 'info')
        return redirect(url_for('artisan_bp.dashboard'))
    
    # Get all active service categories for the form
    service_categories = ServiceCategory.query.filter_by(is_active=True).all()
    
    if request.method == 'GET':
        return render_template('auth/upgrade_to_artisan.html', 
                              categories=service_categories,
                              user=user)
    
    elif request.method == 'POST':
        data = request.form if request.form else request.get_json()
        
        try:
            # 1. Update user type to artisan
            user.user_type = 'artisan'
            user.is_verified = False  # Require verification again
            
            # 2. Create ArtisanProfile
            artisan_profile = ArtisanProfile(
                user_id=user.id,
                category=data['category'],
                skills=data.get('skills', ''),
                experience_years=int(data.get('experience_years', 0)),
                availability='available'
            )
            
            # Handle credentials
            if data.get('credentials'):
                credentials_list = [c.strip() for c in data['credentials'].split(',') if c.strip()]
                artisan_profile.credentials = json.dumps(credentials_list)
            
            # Handle portfolio images
            portfolio_images = []
            if 'portfolio_images' in request.files:
                uploaded_files = request.files.getlist('portfolio_images')
                for file in uploaded_files:
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        file_path = os.path.join(
                            current_app.config['UPLOAD_FOLDER'], 
                            'portfolio', 
                            filename
                        )
                        file.save(file_path)
                        portfolio_images.append(f'portfolio/{filename}')
            
            if portfolio_images:
                artisan_profile.portfolio_images = json.dumps(portfolio_images)
            
            db.session.add(artisan_profile)
            
            # 3. Create notification for admin
            notification = Notification(
                user_id='admin',  # Replace with actual admin ID
                title='Customer Upgraded to Artisan',
                message=f'{user.full_name} ({user.email}) has upgraded to artisan in {artisan_profile.category}',
                notification_type='artisan_upgrade',
                related_id=user.id
            )
            db.session.add(notification)
            
            # 4. Create notification for user
            user_notification = Notification(
                user_id=user.id,
                title='Artisan Registration Submitted',
                message='Your artisan registration is pending admin verification.',
                notification_type='upgrade_pending'
            )
            db.session.add(user_notification)
            
            db.session.commit()
            
            if request.is_json:
                return jsonify({
                    'message': 'Artisan registration submitted for verification',
                    'user': user.to_dict()
                }), 200
            else:
                flash('Artisan registration submitted for verification!', 'success')
                return redirect(url_for('user_bp.dashboard'))
                
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return jsonify({'error': str(e)}), 500
            else:
                flash(f'Error: {str(e)}', 'danger')
                return render_template('auth/upgrade_to_artisan.html',
                                      categories=service_categories,
                                      user=user)
            
# Service Request Routes
@user_bp.route('/dashboard')
@login_required
def dashboard():
    if not isinstance(current_user, User):
        if request.is_json:
            return jsonify({'error': 'User access required'}), 403
        else:
            flash('User access required', 'danger')
            if current_user.user_type == 'admin':
                return redirect(url_for('admin_bp.admin_dashboard'))
            if current_user.user_type == 'artisan':
                return redirect(url_for('artisan_bp.artisan_dashboard'))
            return redirect(url_for('main_bp.home'))  # Add a home route or login
    
    # Get user stats
    stats = get_user_stats(current_user.id)
    
    # Get recent requests (last 5)
    recent_requests = ServiceRequest.query.filter_by(user_id=current_user.id)\
        .order_by(ServiceRequest.created_at.desc())\
        .limit(5).all()
    
    # Get active categories
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    
    # Get unread notifications count
    unread_notifications = Notification.query.filter_by(
    user_id=current_user.id,
    is_read=False
    ).count()
    
    if request.is_json:
        return jsonify({
            'user': current_user.to_dict(),
            'stats': stats,
            'recent_requests': [req.to_dict() for req in recent_requests]
        })
    else:
        return render_template('user/dashboard.html',
                               stats=stats,
                               recent_requests=recent_requests,
                               categories=categories,
                               user=current_user,
                               unread_notifications=unread_notifications)
    
@user_bp.route('/services')
@login_required
def services():
    """View all service categories"""
    
    categories = ServiceCategory.query.filter_by(is_active=True).order_by(ServiceCategory.name).all()
    
    # Get stats
    active_artisans = User.query.filter_by(user_type='artisan', is_active=True, is_verified=True).count()
    completed_jobs = ServiceRequest.query.filter_by(status='completed').count()
    available_categories = ServiceCategory.query.filter_by(is_active=True).count()
    
    return render_template('user/services.html',
                         categories=categories,
                         available_categories=available_categories,
                         active_artisans=active_artisans,
                         completed_jobs=completed_jobs)


@user_bp.route('/request/<request_id>')
@login_required
def view_request(request_id):
    """View a specific service request"""
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    # Ensure user owns this request
    if service_request.user_id != current_user.id and current_user.user_type != 'admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user_bp.my_requests'))
    
    return render_template('user/view_request.html', request=service_request)

@user_bp.route('/completed-requests')
@login_required
def completed_requests():
    """View completed requests for feedback"""
    completed = ServiceRequest.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).order_by(ServiceRequest.completed_at.desc()).all()
    
    return render_template('user/completed_requests.html', requests=completed)

@user_bp.route('/my-requests')
@login_required
def my_requests():
    """View all user requests"""
    all_requests = ServiceRequest.query.filter_by(user_id=current_user.id)\
        .order_by(ServiceRequest.created_at.desc()).all()
    
    return render_template('user/my_requests.html', requests=all_requests)

@user_bp.route('/cancel-request', methods=['POST'])
@login_required
def cancel_service_request():
    """Cancel a service request"""
    data = request.get_json()
    request_id = data.get('request_id')
    
    if not request_id:
        return jsonify({'error': 'No request ID provided'}), 400
    
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    # Ensure user owns this request
    if service_request.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if service_request.status not in ['pending', 'assigned']:
        return jsonify({'error': 'Cannot cancel request in current status'}), 400
    
    service_request.status = 'cancelled'
    db.session.commit()
    
    return jsonify({'message': 'Request cancelled successfully'})

@user_bp.route('/service-request', methods=['GET', 'POST'])
@login_required
def create_service_request():
    if not isinstance(current_user, User):
        flash('User access required', 'danger')
        return redirect(url_for('user_bp.dashboard'))
    
    if request.method == 'GET':
        categories = ServiceCategory.query.filter_by(is_active=True).all()
        return render_template('user/create_request.html', 
                              categories=categories,
                              today=datetime.now().date())
    
    elif request.method == 'POST':
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
        
        if request.is_json:
            return jsonify({
                'message': 'Service request submitted successfully',
                'request': service_request.to_dict()
            }), 201
        else:
            flash('Service request submitted successfully!', 'success')
            return redirect(url_for('user_bp.dashboard'))

@user_bp.route('/service-request/<request_id>', methods=['GET'])
@login_required
def get_service_request(request_id):
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    # Ensure user owns this request
    if service_request.user_id != current_user.id and current_user.user_type != 'admin':
        if request.is_json:
            return jsonify({'error': 'Unauthorized'}), 403
        else:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('user_bp.dashboard'))
    
    if request.is_json:
        return jsonify(service_request.to_dict())
    else:
        return render_template('user/view_request.html', request=service_request)

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
    """Get user notifications"""
    if not isinstance(current_user, User):
        return jsonify({'error': 'User access required'}), 403
    
    # Check if only count is requested
    count_only = request.args.get('count_only', 'false').lower() == 'true'
    
    if count_only:
        unread_count = Notification.query.filter_by(
            user_id=current_user.id,
            user_type='user',
            is_read=False
        ).count()
        
        return jsonify({'unread_count': unread_count})
    
    # Get all notifications
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()

    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    # This week count
    from datetime import datetime, timedelta
    week_ago = datetime.now() - timedelta(days=7)
    this_week_count = sum(1 for n in notifications if n.created_at >= week_ago)
    
    # Important notifications (status updates and artisan assigned)
    important_count = sum(1 for n in notifications if n.notification_type in ['status_update', 'artisan_assigned'])
    
    if request.is_json:
        return jsonify({
            'notifications': [n.to_dict() for n in notifications],
            'stats': {
                'unread_count': unread_count,
                'this_week_count': this_week_count,
                'important_count': important_count
            }
        })
    else:
        return render_template('user/notifications.html',
                             notifications=notifications,
                             unread_count=unread_count,
                             this_week_count=this_week_count,
                             important_count=important_count)

@user_bp.route('/notifications/<notification_id>/read', methods=['PUT'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    return jsonify({'message': 'Notification marked as read'})

@user_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).all()
    
    for notification in notifications:
        notification.is_read = True
    
    db.session.commit()
    
    return jsonify({
        'message': f'{len(notifications)} notifications marked as read',
        'count': len(notifications)
    })

@user_bp.route('/notifications/<notification_id>', methods=['DELETE'])
@login_required
def delete_notification(notification_id):
    """Delete a notification"""
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({'message': 'Notification deleted'})

@user_bp.route('/notifications/clear-read', methods=['DELETE'])
@login_required
def clear_read_notifications():
    """Clear all read notifications"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        user_type='user',
        is_read=True
    ).all()
    
    count = len(notifications)
    for notification in notifications:
        db.session.delete(notification)
    
    db.session.commit()
    
    return jsonify({
        'message': f'{count} read notifications cleared',
        'count': count
    })

@user_bp.route('/notifications/clear-all', methods=['DELETE'])
@login_required
def clear_all_notifications():
    """Clear all notifications"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        user_type='user'
    ).all()
    
    count = len(notifications)
    for notification in notifications:
        db.session.delete(notification)
    
    db.session.commit()
    
    return jsonify({
        'message': f'{count} notifications cleared',
        'count': count
    })

@user_bp.route('/notifications/settings', methods=['POST'])
@login_required
def update_notification_settings():
    """Update notification settings"""
    data = request.get_json()
    
    # You would save these to UserSettings model
    # For now, just acknowledge
    return jsonify({'message': 'Notification settings updated'})

# Profile Management
@user_bp.route('/profile', methods=['GET', 'PUT'])
@login_required
def profile():
    """Profile management"""
    if not isinstance(current_user, User):
        flash('User access required', 'danger')
        return redirect(url_for('user_bp.dashboard'))
    
    if request.method == 'GET':
        # Get user stats
        from models import ServiceRequest
        stats = {
            'total_requests': ServiceRequest.query.filter_by(user_id=current_user.id).count(),
            'completed_requests': ServiceRequest.query.filter_by(user_id=current_user.id, status='completed').count()
        }
        
        # Calculate months since joined
        from datetime import datetime
        months_since = (datetime.now().year - current_user.created_at.year) * 12 + \
                      (datetime.now().month - current_user.created_at.month)
        
        # Mock data for settings (you should implement your own logic)
        notification_settings = {
            'email': [
                {'id': 'new_request', 'name': 'New Requests', 'description': 'When you submit a new request', 'enabled': True},
                {'id': 'status_update', 'name': 'Status Updates', 'description': 'When your request status changes', 'enabled': True},
                {'id': 'artisan_assigned', 'name': 'Artisan Assigned', 'description': 'When an artisan is assigned', 'enabled': True},
                {'id': 'promotions', 'name': 'Promotions', 'description': 'Special offers and discounts', 'enabled': False}
            ],
            'push': [
                {'id': 'messages', 'name': 'Messages', 'description': 'New messages from artisans', 'enabled': True},
                {'id': 'reminders', 'name': 'Reminders', 'description': 'Service reminders', 'enabled': True}
            ],
            'sms': [
                {'id': 'urgent', 'name': 'Urgent Updates', 'description': 'Critical service updates', 'enabled': True}
            ]
        }
        
        privacy_settings = {
            'profile_visibility': 'artisans',
            'share_analytics': True,
            'marketing_emails': False
        }
        
        current_session = {
            'device': 'Chrome on Windows',
            'location': 'Lagos, Nigeria',
            'started': '2 hours ago'
        }
        
        # Add preferences to context
        preferences = {
            'default_location': current_user.address if current_user.address else '',
            'contact_method': 'email'  # Default value
        }
        
        return render_template('user/profile.html',
                             stats=stats,
                             member_since=max(1, months_since),
                             notification_settings=notification_settings,
                             privacy_settings=privacy_settings,
                             current_session=current_session,
                             two_factor_enabled=False,
                             preferences=preferences)
    
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

@user_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    data = request.get_json()
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    confirm_password = data.get('confirm_password')
    
    if not current_password or not new_password:
        return jsonify({'error': 'All fields are required'}), 400
    
    if new_password != confirm_password:
        return jsonify({'error': 'Passwords do not match'}), 400
    
    if not current_user.check_password(current_password):
        return jsonify({'error': 'Current password is incorrect'}), 400
    
    if len(new_password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    current_user.set_password(new_password)
    db.session.commit()
    
    return jsonify({'message': 'Password updated successfully'})

@user_bp.route('/delete-account', methods=['DELETE'])
@login_required
def delete_account():
    """Delete user account"""
    # Soft delete - mark as inactive instead of actual deletion
    current_user.is_active = False
    db.session.commit()
    
    logout_user()
    return jsonify({'message': 'Account deleted successfully'})



