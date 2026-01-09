# user_routes.py

from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app
import os
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import db, User, ServiceRequest, ServiceCategory, Notification, ArtisanProfile, ServiceRequest, Payment, ArtisanKYCVerification, VerificationRequest
from datetime import datetime, timedelta, timezone
import json
from forms import LoginForm, UserRegistrationForm, ServiceRequestForm, BankAccountForm, ArtisanRegistrationForm, ServiceRequestForm, PaymentForm

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
            nin=data.get('nin', ''),  # CRITICAL: Store NIN
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
            
            # Update user address if provided
            if data.get('address'):
                user.address = data['address']
            
            # 2. Create ArtisanProfile with KYC and bank details
            artisan_profile = ArtisanProfile(
                user_id=user.id,
                category=data['category'],
                skills=data.get('skills', ''),
                experience_years=int(data.get('experience_years', 0)),
                availability='available' if data.get('availability') else 'unavailable',
                
                # KYC Information
                nin=data.get('nin', ''),
                date_of_birth=datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date() if data.get('date_of_birth') else None,
                state_of_origin=data.get('state_of_origin', ''),
                lga_of_origin=data.get('lga_of_origin', ''),
                kyc_status='pending',  # Start with pending status
                
                # Bank Information
                bank_name=data.get('bank_name', ''),
                account_name=data.get('account_name', ''),
                account_number=data.get('account_number', '')
            )
            
            # Handle "Other" bank name
            if data.get('bank_name') == 'other' and data.get('other_bank_name'):
                artisan_profile.bank_name = data['other_bank_name']
            
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
                        # Create portfolio directory if it doesn't exist
                        portfolio_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'portfolio')
                        os.makedirs(portfolio_dir, exist_ok=True)
                        
                        file_path = os.path.join(portfolio_dir, filename)
                        file.save(file_path)
                        portfolio_images.append(f'portfolio/{filename}')
            
            if portfolio_images:
                artisan_profile.portfolio_images = json.dumps(portfolio_images)
            
            # Handle KYC document uploads (if provided during upgrade)
            kyc_docs = []
            if 'nin_front_image' in request.files and request.files['nin_front_image'].filename:
                file = request.files['nin_front_image']
                filename = secure_filename(file.filename)
                kyc_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'kyc')
                os.makedirs(kyc_dir, exist_ok=True)
                file_path = os.path.join(kyc_dir, filename)
                file.save(file_path)
                artisan_profile.nin_front_image = f'kyc/{filename}'
                kyc_docs.append(f'kyc/{filename}')
            
            # Add more KYC document handling as needed...
            
            # Set KYC submission timestamp
            artisan_profile.kyc_submitted_at = datetime.now(timezone.utc)
            
            db.session.add(artisan_profile)
            
            # 3. Create a KYC verification record for admin review
            kyc_verification = ArtisanKYCVerification(
                artisan_profile_id=artisan_profile.id,
                nin=data.get('nin', ''),
                date_of_birth=datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date() if data.get('date_of_birth') else None,
                state_of_origin=data.get('state_of_origin', ''),
                lga_of_origin=data.get('lga_of_origin', ''),
                status='pending',
                
                # Bank information for verification
                bank_name=artisan_profile.bank_name,
                account_name=artisan_profile.account_name,
                account_number=artisan_profile.account_number,
                
                # Document URLs (would need to be uploaded separately or point to profile)
                nin_front_image=artisan_profile.nin_front_image if artisan_profile.nin_front_image else '',
                nin_back_image=artisan_profile.nin_back_image if artisan_profile.nin_back_image else '',
                passport_photo=artisan_profile.passport_photo if artisan_profile.passport_photo else '',
                proof_of_address=artisan_profile.proof_of_address if artisan_profile.proof_of_address else ''
            )
            
            db.session.add(kyc_verification)
            
            # 4. Create notification for admin
            notification = Notification(
                user_id='admin',  # Replace with actual admin ID or find admin users
                title='Customer Upgraded to Artisan - KYC Pending',
                message=f'{user.full_name} ({user.email}) has upgraded to artisan in {artisan_profile.category}. KYC verification required.',
                notification_type='artisan_upgrade_kyc',
                related_id=user.id
            )
            db.session.add(notification)
            
            # 5. Create notification for user
            user_notification = Notification(
                user_id=user.id,
                title='Artisan Registration Submitted',
                message='Your artisan registration is pending admin and KYC verification. Please upload required documents when prompted.',
                notification_type='upgrade_pending_kyc'
            )
            db.session.add(user_notification)
            
            # 6. Create verification request for admin dashboard
            verification_data = {
                'category': artisan_profile.category,
                'skills': artisan_profile.skills,
                'experience_years': artisan_profile.experience_years,
                'nin': artisan_profile.nin,
                'state_of_origin': artisan_profile.state_of_origin,
                'lga_of_origin': artisan_profile.lga_of_origin,
                'bank_name': artisan_profile.bank_name,
                'account_name': artisan_profile.account_name,
                'account_number': artisan_profile.account_number
            }
            
            verification_request = VerificationRequest(
                user_id=user.id,
                status='pending',
                request_data=json.dumps(verification_data),
                admin_notes=f'Upgraded from customer to artisan. KYC status: {artisan_profile.kyc_status}'
            )
            db.session.add(verification_request)
            
            db.session.commit()
            
            if request.is_json:
                return jsonify({
                    'message': 'Artisan registration submitted for verification',
                    'kyc_required': True,
                    'user': user.to_dict(),
                    'artisan_profile': artisan_profile.to_dict()
                }), 200
            else:
                flash('Artisan registration submitted for verification! KYC documents may be required.', 'success')
                return redirect(url_for('user_bp.dashboard'))
                
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error upgrading to artisan: {str(e)}", exc_info=True)
            
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
        .join(ServiceCategory, ServiceRequest.category_id == ServiceCategory.id)\
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
    
    form = ServiceRequestForm()
    
    # Populate category choices
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    form.category_id.choices = [(cat.id, cat.name) for cat in categories] + [('', 'Select category')]
    
    if request.method == 'GET':
        return render_template('user/create_request.html', 
                              form=form,
                              categories=categories,
                              today=datetime.now().date())
    
    elif request.method == 'POST':
        if form.validate_on_submit():
            # Get payment method from form data (it's not in the WTForm)
            payment_method = request.form.get('payment_method', 'cash')
            
            # Create service request
            service_request = ServiceRequest(
                user_id=current_user.id,
                category_id=form.category_id.data,
                title=form.title.data,
                description=form.description.data,
                location=form.location.data,
                preferred_date=form.preferred_date.data,
                preferred_time=form.preferred_time.data,
                status='pending',
                payment_method=payment_method,
                payment_status='pending'
            )
            
            # Handle additional notes
            if form.additional_notes.data:
                service_request.description += f"\n\nAdditional Notes: {form.additional_notes.data}"
            
            db.session.add(service_request)
            db.session.commit()
            
            # Create notifications
            notification = Notification(
                user_id='admin',
                title='New Service Request',
                message=f'New service request from {current_user.full_name}: {service_request.title}',
                notification_type='new_request',
                related_id=service_request.id
            )
            db.session.add(notification)
            
            user_notification = Notification(
                user_id=current_user.id,
                title='Service Request Submitted',
                message=f'Your service request "{service_request.title}" has been submitted.',
                notification_type='request_submitted',
                related_id=service_request.id
            )
            db.session.add(user_notification)
            
            db.session.commit()
            
            flash('Service request submitted successfully!', 'success')
            
            # Redirect based on payment method
            if service_request.payment_method == 'bank_transfer':
                return redirect(url_for('user_bp.make_payment', request_id=service_request.id))
            else:
                return redirect(url_for('user_bp.dashboard'))
        else:
            # Flash form errors
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{getattr(form, field).label.text}: {error}", 'danger')
            return redirect(url_for('user_bp.create_service_request'))
        
def flash_form_errors(form):
    """Flash all form errors"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"{getattr(form, field).label.text}: {error}", 'danger')

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


# Company bank details (store securely in production)
COMPANY_BANK_DETAILS = {
    'account_name': 'Uwaila.com globals',
    'account_number': '1217754667',
    'bank_name': 'Zenith Bank'
}

@user_bp.route('/profile/bank-details', methods=['GET', 'POST'])
@login_required
def manage_bank_details():
    """Manage user bank account details"""
    form = BankAccountForm()
    
    if form.validate_on_submit():
        try:
            current_user.bank_name = form.other_bank_name.data if form.bank_name.data == 'other' else form.bank_name.data
            current_user.account_name = form.account_name.data
            current_user.account_number = form.account_number.data
            
            db.session.commit()
            flash('Bank details updated successfully!', 'success')
            return redirect(url_for('user_bp.profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating bank details: {str(e)}', 'danger')
    
    # Pre-populate form
    if current_user.bank_name:
        form.bank_name.data = current_user.bank_name
        form.account_name.data = current_user.account_name
        form.account_number.data = current_user.account_number
    
    return render_template('user/bank_details.html', form=form)

@user_bp.route('/payment/<request_id>', methods=['GET', 'POST'])
@login_required
def make_payment(request_id):
    """Make payment for a service request"""
    service_request = ServiceRequest.query.get_or_404(request_id)
    
    # Check if user owns this request
    if service_request.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user_bp.dashboard'))
    
    # Check if payment already exists
    existing_payment = Payment.query.filter_by(
        service_request_id=request_id,
        user_id=current_user.id
    ).first()
    
    if existing_payment and existing_payment.payment_status == 'completed':
        flash('Payment already completed for this request', 'info')
        return redirect(url_for('user_bp.view_request', request_id=request_id))
    
    form = PaymentForm()
    amount = service_request.price_estimate or service_request.actual_price or 0
    
    if form.validate_on_submit():
        try:
            # Handle Paystack - show coming soon message
            if form.payment_method.data == 'paystack':
                flash('Paystack integration is coming soon! Please use another payment method.', 'info')
                return redirect(url_for('user_bp.make_payment', request_id=request_id))
            
            # Validate amount
            if float(form.amount.data) <= 0:
                flash('Amount must be greater than 0', 'danger')
                return render_template('user/make_payment.html',
                                     form=form,
                                     request=service_request,
                                     company_details=COMPANY_BANK_DETAILS)
            
            # Create payment record
            payment = Payment(
                service_request_id=request_id,
                user_id=current_user.id,
                amount=float(form.amount.data),
                payment_method=form.payment_method.data,
                payment_type='service_fee',
                payment_status='pending' if form.payment_method.data == 'bank_transfer' else 'completed',
                company_account_name=COMPANY_BANK_DETAILS['account_name'] if form.payment_method.data == 'bank_transfer' else None,
                company_account_number=COMPANY_BANK_DETAILS['account_number'] if form.payment_method.data == 'bank_transfer' else None,
                company_bank_name=COMPANY_BANK_DETAILS['bank_name'] if form.payment_method.data == 'bank_transfer' else None,
                payer_account_name=form.payer_account_name.data if form.payment_method.data == 'bank_transfer' else None,
                payer_account_number=form.payer_account_number.data if form.payment_method.data == 'bank_transfer' else None,
                payer_bank_name=form.payer_bank_name.data if form.payment_method.data == 'bank_transfer' else None,
                transaction_reference=form.transaction_reference.data if form.payment_method.data == 'bank_transfer' else None,
                payment_notes=form.payment_notes.data,
                payment_date=datetime.now(timezone.utc) if form.payment_method.data != 'bank_transfer' else None
            )
            
            # Handle optional receipt upload
            if form.receipt_image.data and form.receipt_image.data.filename:
                file = form.receipt_image.data
                filename = secure_filename(f"receipt_{request_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
                file_path = os.path.join(
                    current_app.config['UPLOAD_FOLDER'],
                    'receipts',
                    filename
                )
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file.save(file_path)
                payment.receipt_image = f'receipts/{filename}'
            
            db.session.add(payment)
            
            # Update service request status if payment is completed
            if form.payment_method.data == 'cash':
                service_request.payment_status = 'paid'
                payment.payment_status = 'completed'
                payment.verified_at = datetime.now(timezone.utc)
            
            # Create notification
            notification = Notification(
                user_id=current_user.id,
                title=f'Payment {payment.payment_status}',
                message=f'Payment of ₦{payment.amount:,.2f} for service request "{service_request.title}" has been {payment.payment_status}.',
                notification_type='payment_update',
                related_id=payment.id
            )
            db.session.add(notification)
            
            # Create admin notification for bank transfers
            if form.payment_method.data == 'bank_transfer':
                admin_notification = Notification(
                    user_id='admin',  # Replace with actual admin user ID
                    title='Bank Transfer Payment Pending Verification',
                    message=f'User {current_user.full_name} has made a bank transfer payment of ₦{payment.amount:,.2f} for request #{request_id}. Receipt: {payment.receipt_image if payment.receipt_image else "Not uploaded yet"}',
                    notification_type='payment_verification',
                    related_id=payment.id
                )
                db.session.add(admin_notification)
            
            db.session.commit()
            
            flash('Payment submitted successfully!', 'success')
            
            if form.payment_method.data == 'bank_transfer':
                return redirect(url_for('user_bp.payment_confirmation', payment_id=payment.id))
            else:
                return redirect(url_for('user_bp.view_request', request_id=request_id))
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing payment: {str(e)}', 'danger')
            return render_template('user/make_payment.html',
                                 form=form,
                                 request=service_request,
                                 company_details=COMPANY_BANK_DETAILS)
    elif request.method == 'POST':
        # Form validation failed
        flash('Please correct the errors in the form', 'danger')
    
    # Pre-populate form for GET request
    if request.method == 'GET':
        form.amount.data = amount
    
    return render_template('user/make_payment.html',
                         form=form,
                         request=service_request,
                         company_details=COMPANY_BANK_DETAILS)

@user_bp.route('/payment/confirmation/<payment_id>')
@login_required
def payment_confirmation(payment_id):
    """Show payment confirmation page"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Check if user owns this payment
    if payment.user_id != current_user.id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user_bp.dashboard'))
    
    return render_template('user/payment_confirmation.html',
                         payment=payment,
                         company_details=COMPANY_BANK_DETAILS)

@user_bp.route('/payment/upload-receipt/<payment_id>', methods=['POST'])
@login_required
def upload_payment_receipt(payment_id):
    """Upload payment receipt for bank transfer"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Check if user owns this payment
    if payment.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if 'receipt_image' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['receipt_image']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        filename = secure_filename(f"receipt_{payment_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            'receipts',
            filename
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        
        payment.receipt_image = f'receipts/{filename}'
        payment.payment_status = 'processing'
        
        # Update notification
        notification = Notification(
            user_id='admin',
            title='Payment Receipt Uploaded',
            message=f'Receipt uploaded for payment #{payment.receipt_number} by {current_user.full_name}',
            notification_type='receipt_uploaded',
            related_id=payment.id
        )
        db.session.add(notification)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Receipt uploaded successfully',
            'receipt_url': url_for('static', filename=f'uploads/receipts/{filename}')
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@user_bp.route('/payments/history')
@login_required
def payment_history():
    """View payment history"""
    payments = Payment.query.filter_by(user_id=current_user.id)\
        .order_by(Payment.created_at.desc())\
        .all()
    
    return render_template('user/payment_history.html', payments=payments)

@user_bp.route('/payment/<payment_id>')
@login_required
def view_payment(payment_id):
    """View payment details"""
    payment = Payment.query.get_or_404(payment_id)
    
    # Check if user owns this payment
    if payment.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('user_bp.dashboard'))
    
    return render_template('user/view_payment.html', payment=payment)