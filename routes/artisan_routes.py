from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, ServiceRequest, ServiceCategory, Notification, ArtisanProfile, Withdrawal, PaymentTransaction, Review, AccountDeactivation, VerificationRequest
import json
import os
from werkzeug.utils import secure_filename
from PIL import Image
import io
import re
from extension import app

import cloudinary
import cloudinary.uploader
import cloudinary.api

from datetime import datetime, timedelta, timezone


artisan_bp = Blueprint('artisan_bp', __name__)

# Configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB
MAX_PORTFOLIO_IMAGES = 20

def allowed_file(filename):
    """Check if the file extension is allowed"""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def validate_file(file):
    """Simple file validation"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    MAX_SIZE = 16 * 1024 * 1024  # 16MB
    
    if not file.filename:
        return False, "No filename"
    
    if '.' not in file.filename:
        return False, "Invalid file"
    
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > MAX_SIZE:
        return False, f"File too large (max 16MB)"
    
    return True, "Valid"


def save_image_locally(file, artisan_id):
    """Save image locally for development"""
    try:
        from werkzeug.utils import secure_filename
        from datetime import datetime
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_name = f"{artisan_id}_{timestamp}_{filename}"
        
        # Create directory if needed
        upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'portfolio')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(upload_dir, unique_name)
        file.save(file_path)
        
        # Return relative URL
        return f"/static/uploads/portfolio/{unique_name}"
        
    except Exception as e:
        print(f"Local save error: {e}")
        return None


def upload_to_cloudinary(file, artisan_id):
    """Upload image to Cloudinary for production"""
    try:
        import cloudinary.uploader
        from datetime import datetime
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result = cloudinary.uploader.upload(
            file,
            folder=f"portfolio/{artisan_id}",
            public_id=f"{artisan_id}_{timestamp}",
            transformation=[
                {'width': 1200, 'crop': 'limit'},
                {'quality': 'auto:good'}
            ]
        )
        return result['secure_url']
        
    except Exception as e:
        print(f"Cloudinary upload error: {e}")
        return None


def get_portfolio_images(user):
    """Get portfolio images from user"""
    try:
        if user.portfolio_images:
            return json.loads(user.portfolio_images)
    except:
        return []
    return []

def save_portfolio_images(user, images):
    """Save portfolio images to user with proper error handling"""
    try:
        user.portfolio_images = json.dumps(images)
        db.session.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Database error saving portfolio: {str(e)}")
        db.session.rollback()
        return False


        
# Artisan Authentication Middleware
def artisan_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.user_type != 'artisan':
            if request.is_json:
                return jsonify({'error': 'Artisan access required'}), 403
            else:
                return render_template('error.html', message='Artisan access required'), 403
        return f(*args, **kwargs)
    return decorated

# ARTISAN REGISTRATION
@artisan_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Get all active service categories for the form
    service_categories = ServiceCategory.query.filter_by(is_active=True).all()
    
    if request.method == 'GET':
        return render_template('auth/artisan_register.html', 
                              categories=service_categories)

    elif request.method == 'POST':
        data = request.form if request.form else request.get_json()
        
        # Check if user already exists
        if User.query.filter_by(email=data.get('email')).first():
            if request.is_json:
                return jsonify({'error': 'Email already registered'}), 400
            else:
                return render_template('auth/artisan_register.html', 
                                      categories=service_categories,
                                      error='Email already registered')
        
        # 1. Create new User (base user)
        user = User(
            email=data['email'],
            phone=data['phone'],
            full_name=data['full_name'],
            address=data.get('address', ''),
            user_type='artisan',  # CRITICAL: Set user_type
            is_verified=False  # Requires admin verification
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.flush()  # Get user ID without committing
        
        # 2. Create ArtisanProfile with artisan-specific fields
        artisan_profile = ArtisanProfile(
            user_id=user.id,
            category=data['category'],
            skills=data.get('skills', ''),
            experience_years=int(data.get('experience_years', 0)),
            availability='available'
        )
        
        # Handle credentials (JSON array)
        if data.get('credentials'):
            credentials_list = [c.strip() for c in data['credentials'].split(',') if c.strip()]
            artisan_profile.credentials = json.dumps(credentials_list)
        
        # Handle portfolio images
        portfolio_images = []
        if 'portfolio_images' in request.files:
            uploaded_files = request.files.getlist('portfolio_images')
            for file in uploaded_files:
                if file and file.filename:
                    # Save file logic here
                    filename = secure_filename(file.filename)
                    # Save to upload folder
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
        
        # Create notification for admin
        notification = Notification(
            user_id='admin',  # You need to get actual admin user ID
            title='New Artisan Registration',
            message=f'New artisan registered: {user.full_name} ({artisan_profile.category})',
            notification_type='new_artisan',
            related_id=user.id
        )
        db.session.add(notification)
        
        # Create welcome notification for artisan
        artisan_notification = Notification(
            user_id=user.id,
            title='Registration Successful',
            message='Your registration is pending admin verification.',
            notification_type='registration_pending'
        )
        db.session.add(artisan_notification)
        
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'message': 'Registration submitted for verification',
                'user': user.to_dict()
            }), 201
        else:
            return render_template('auth/registration_success.html',
                                  message='Registration submitted for verification')
 
@artisan_bp.route('/dashboard')
@artisan_required
def artisan_dashboard():
    # Get statistics
    assigned_jobs = ServiceRequest.query.filter_by(
        artisan_id=current_user.id,
        status='assigned'
    ).count()
    
    active_jobs = ServiceRequest.query.filter_by(
        artisan_id=current_user.id,
        status='in_progress'
    ).count()
    
    completed_jobs = ServiceRequest.query.filter_by(
        artisan_id=current_user.id,
        status='completed'
    ).count()
    
    # Calculate earnings (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    monthly_earnings = ServiceRequest.query.filter(
        ServiceRequest.artisan_id == current_user.id,
        ServiceRequest.status == 'completed',
        ServiceRequest.created_at >= thirty_days_ago
    ).with_entities(db.func.sum(ServiceRequest.actual_price)).scalar() or 0
    
    # Total earnings
    total_earnings = ServiceRequest.query.filter(
        ServiceRequest.artisan_id == current_user.id,
        ServiceRequest.status == 'completed'
    ).with_entities(db.func.sum(ServiceRequest.actual_price)).scalar() or 0
    
    # Recent jobs
    recent_jobs = ServiceRequest.query.filter_by(artisan_id=current_user.id)\
        .order_by(ServiceRequest.created_at.desc())\
        .limit(5)\
        .all()
    
    # Notifications
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc())\
     .limit(5)\
     .all()
    
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    if request.is_json:
        return jsonify({
            'stats': {
                'assigned_jobs': assigned_jobs,
                'active_jobs': active_jobs,
                'completed_jobs': completed_jobs,
                'monthly_earnings': monthly_earnings,
                'total_earnings': total_earnings
            },
            'recent_jobs': [job.to_dict() for job in recent_jobs],
            'unread_notifications': unread_count
        })
    else:
        return render_template('artisan/dashboard.html',
                              stats={
                                  'assigned_jobs': assigned_jobs,
                                  'active_jobs': active_jobs,
                                  'completed_jobs': completed_jobs,
                                  'monthly_earnings': monthly_earnings,
                                  'total_earnings': total_earnings
                              },
                              recent_jobs=recent_jobs,
                              notifications=notifications,
                              unread_notifications=unread_count)

# Add these helper functions if not already defined
def calculate_response_rate(artisan_id):
    """Calculate artisan's response rate to job requests"""
    # Get all jobs assigned to artisan in last 30 days
    recent_jobs = ServiceRequest.query.filter(
        ServiceRequest.artisan_id == artisan_id,
        ServiceRequest.created_at >= datetime.now(timezone.utc) - timedelta(days=30)
    ).all()
    
    if not recent_jobs:
        return 0
    
    # Count jobs where artisan responded within 24 hours
    responded_jobs = 0
    for job in recent_jobs:
        # Check if there's a response record or status change within 24 hours
        # This is simplified - you might have a better metric
        if job.updated_at and job.created_at:
            response_time = job.updated_at - job.created_at
            if response_time <= timedelta(hours=24):
                responded_jobs += 1
    
    return round((responded_jobs / len(recent_jobs)) * 100, 1)

def calculate_completion_rate(artisan_id):
    """Calculate artisan's job completion rate"""
    total_assigned = ServiceRequest.query.filter_by(
        artisan_id=artisan_id
    ).count()
    
    total_completed = ServiceRequest.query.filter_by(
        artisan_id=artisan_id,
        status='completed'
    ).count()
    
    if total_assigned == 0:
        return 0
    
    return round((total_completed / total_assigned) * 100, 1)

@artisan_bp.route('/profile', methods=['GET', 'PUT', 'POST'])
@artisan_required
def artisan_profile():
    if request.method == 'GET':
        # Get artisan profile data
        artisan_profile = current_user.artisan_profile
        
        if not artisan_profile:
            return jsonify({'error': 'Artisan profile not found'}), 404
        
        # Calculate profile completion percentage
        profile_fields = [
            ('full_name', current_user.full_name),
            ('email', current_user.email),
            ('phone', current_user.phone),
            ('category', artisan_profile.category),
            ('skills', artisan_profile.skills),
            ('experience_years', artisan_profile.experience_years),
            ('portfolio_images', artisan_profile.portfolio_images),
            ('credentials', artisan_profile.credentials),
        ]
        
        completed_fields = sum(1 for field, value in profile_fields if value)
        total_fields = len(profile_fields)
        profile_completion = int((completed_fields / total_fields) * 100)
        
        # Get categories for dropdown
        categories = ServiceCategory.query.filter_by(is_active=True).all()
        
        # Get statistics for profile page
        stats = {
            'completed_jobs': ServiceRequest.query.filter_by(
                artisan_id=current_user.id,
                status='completed'
            ).count(),
            'total_earnings': float(db.session.query(
                db.func.coalesce(db.func.sum(ServiceRequest.actual_price), 0)
            ).filter(
                ServiceRequest.artisan_id == current_user.id,
                ServiceRequest.status == 'completed',
                ServiceRequest.actual_price.isnot(None)
            ).scalar()),
            'active_jobs': ServiceRequest.query.filter_by(
                artisan_id=current_user.id,
                status='in_progress'
            ).count(),
            'pending_jobs': ServiceRequest.query.filter_by(
                artisan_id=current_user.id,
                status='assigned'
            ).count(),
            'average_rating': float(artisan_profile.rating) if artisan_profile.rating else 0.0,
            'response_rate': calculate_response_rate(current_user.id),
            'completion_rate': calculate_completion_rate(current_user.id),
        }
        
        if request.is_json:
            artisan_data = current_user.to_dict()
            # Add artisan profile specific data
            artisan_data.update({
                'category': artisan_profile.category,
                'skills': artisan_profile.skills,
                'experience_years': artisan_profile.experience_years,
                'availability': artisan_profile.availability,
                'hourly_rate': artisan_profile.hourly_rate,
                'min_service_fee': artisan_profile.min_service_fee,
                'credentials': json.loads(artisan_profile.credentials) if artisan_profile.credentials else [],
                'portfolio_images': json.loads(artisan_profile.portfolio_images) if artisan_profile.portfolio_images else [],
                'rating': artisan_profile.rating,
                'total_jobs': artisan_profile.total_jobs,
                'completed_jobs': artisan_profile.completed_jobs,
            })
            return jsonify({
                'artisan': artisan_data,
                'profile_completion': profile_completion,
                'stats': stats,
                'categories': [cat.to_dict() for cat in categories]
            })
        else:
            # Parse portfolio images and credentials for template
            portfolio_images = json.loads(artisan_profile.portfolio_images) if artisan_profile.portfolio_images else []
            credentials = json.loads(artisan_profile.credentials) if artisan_profile.credentials else []
            
            return render_template('artisan/profile.html',
                                  artisan=current_user,
                                  artisan_profile=artisan_profile,
                                  profile_completion=profile_completion,
                                  stats=stats,
                                  categories=categories,
                                  portfolio_images=portfolio_images,
                                  credentials=credentials)
    
    elif request.method == 'PUT':
        if not current_user.artisan_profile:
            return jsonify({'error': 'Artisan profile not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        artisan_profile = current_user.artisan_profile
        
        try:
            # Update user fields
            if 'full_name' in data:
                if not data['full_name'].strip():
                    return jsonify({'error': 'Full name cannot be empty'}), 400
                current_user.full_name = data['full_name'].strip()
            
            if 'phone' in data:
                if not re.match(r'^\+?[\d\s\-\(\)]{10,}$', str(data['phone'])):
                    return jsonify({'error': 'Invalid phone number format'}), 400
                current_user.phone = data['phone']
            
            if 'email' in data:
                if data['email'] != current_user.email:
                    existing = User.query.filter(
                        User.email == data['email'],
                        User.id != current_user.id
                    ).first()
                    if existing:
                        return jsonify({'error': 'Email already registered'}), 400
                    current_user.email = data['email']
            
            # Update artisan profile fields
            if 'category' in data:
                # Verify category exists and is active
                category = ServiceCategory.query.filter_by(
                    name=data['category'],
                    is_active=True
                ).first()
                if not category:
                    return jsonify({'error': 'Invalid service category'}), 400
                artisan_profile.category = data['category']
            
            if 'skills' in data:
                artisan_profile.skills = data['skills']
            
            if 'experience_years' in data:
                try:
                    years = int(data['experience_years'])
                    if years < 0 or years > 50:
                        return jsonify({'error': 'Experience years must be between 0 and 50'}), 400
                    artisan_profile.experience_years = years
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid experience years'}), 400
            
            if 'availability' in data:
                valid_availabilities = ['available', 'busy', 'offline']
                if data['availability'] not in valid_availabilities:
                    return jsonify({'error': 'Invalid availability status'}), 400
                artisan_profile.availability = data['availability']
            
            if 'hourly_rate' in data:
                try:
                    rate = float(data['hourly_rate'])
                    if rate < 0:
                        return jsonify({'error': 'Hourly rate cannot be negative'}), 400
                    artisan_profile.hourly_rate = rate
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid hourly rate'}), 400
            
            if 'min_service_fee' in data:
                try:
                    fee = float(data['min_service_fee'])
                    if fee < 0:
                        return jsonify({'error': 'Minimum service fee cannot be negative'}), 400
                    artisan_profile.min_service_fee = fee
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid minimum service fee'}), 400
            
            # Handle credentials update
            if 'credentials' in data:
                if isinstance(data['credentials'], list):
                    # Validate each credential is a string
                    valid_credentials = []
                    for cred in data['credentials']:
                        if isinstance(cred, str) and cred.strip():
                            valid_credentials.append(cred.strip())
                    artisan_profile.credentials = json.dumps(valid_credentials)
                elif isinstance(data['credentials'], str):
                    # Handle comma-separated string
                    creds = [c.strip() for c in data['credentials'].split(',') if c.strip()]
                    artisan_profile.credentials = json.dumps(creds)
                else:
                    return jsonify({'error': 'Invalid credentials format'}), 400
            
            # Handle portfolio images update (URLs only in JSON)
            if 'portfolio_images' in data:
                if isinstance(data['portfolio_images'], list):
                    # Limit to 20 images and validate each is a string
                    valid_images = []
                    for img in data['portfolio_images'][:20]:
                        if isinstance(img, str) and img.strip():
                            valid_images.append(img.strip())
                    artisan_profile.portfolio_images = json.dumps(valid_images)
                else:
                    return jsonify({'error': 'Invalid portfolio images format'}), 400
            
            # Update timestamps
            current_user.updated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            
            # Return updated data
            artisan_data = current_user.to_dict()
            artisan_data.update({
                'category': artisan_profile.category,
                'skills': artisan_profile.skills,
                'experience_years': artisan_profile.experience_years,
                'availability': artisan_profile.availability,
                'hourly_rate': artisan_profile.hourly_rate,
                'min_service_fee': artisan_profile.min_service_fee,
                'credentials': json.loads(artisan_profile.credentials) if artisan_profile.credentials else [],
                'portfolio_images': json.loads(artisan_profile.portfolio_images) if artisan_profile.portfolio_images else [],
            })
            
            return jsonify({
                'message': 'Profile updated successfully',
                'artisan': artisan_data
            })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Update failed: {str(e)}'}), 500
    
    elif request.method == 'POST':
        # Handle specific POST actions like changing password, deactivating account, etc.
        action = request.args.get('action') or (request.get_json() or {}).get('action')
        
        if not action:
            return jsonify({'error': 'No action specified'}), 400
        
        if action == 'change-password':
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            
            if not current_password or not new_password:
                return jsonify({'error': 'Both current and new password are required'}), 400
            
            if not current_user.check_password(current_password):
                return jsonify({'error': 'Current password is incorrect'}), 400
            
            if len(new_password) < 8:
                return jsonify({'error': 'New password must be at least 8 characters long'}), 400
            
            current_user.set_password(new_password)
            current_user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            return jsonify({'message': 'Password changed successfully'})
        
        elif action == 'deactivate':
            data = request.get_json() or {}
            reason = data.get('reason', '')
            
            # Create deactivation record
            deactivation = AccountDeactivation(
                user_id=current_user.id,
                reason=reason,
                is_permanent=False
            )
            db.session.add(deactivation)
            
            # Deactivate account
            current_user.is_active = False
            db.session.commit()
            
            # Create notification
            notification = Notification(
                user_id=current_user.id,
                title='Account Deactivated',
                message='Your artisan account has been deactivated.',
                notification_type='account_deactivated'
            )
            db.session.add(notification)
            db.session.commit()
            
            return jsonify({'message': 'Account deactivated successfully'})
        
        elif action == 'request-verification':
            # Check if already verified
            if current_user.is_verified:
                return jsonify({'error': 'Account is already verified'}), 400
            
            # Check if verification was recently requested
            recent_request = VerificationRequest.query.filter_by(
                user_id=current_user.id,
                status='pending'
            ).filter(
                VerificationRequest.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
            ).first()
            
            if recent_request:
                return jsonify({'error': 'Verification request already pending. Please wait 7 days.'}), 400
            
            # Create verification request with artisan data
            verification_data = {
                'full_name': current_user.full_name,
                'category': current_user.artisan_profile.category if current_user.artisan_profile else 'Unknown',
                'experience_years': current_user.artisan_profile.experience_years if current_user.artisan_profile else 0,
                'skills': current_user.artisan_profile.skills if current_user.artisan_profile else '',
                'credentials': json.loads(current_user.artisan_profile.credentials) if current_user.artisan_profile and current_user.artisan_profile.credentials else [],
                'portfolio_images': json.loads(current_user.artisan_profile.portfolio_images) if current_user.artisan_profile and current_user.artisan_profile.portfolio_images else []
            }
            
            verification_request = VerificationRequest(
                user_id=current_user.id,
                status='pending',
                request_data=json.dumps(verification_data)
            )
            db.session.add(verification_request)
            
            # Create notification for admin (you need to get actual admin ID)
            # For now, find the first admin user
            admin = User.query.filter_by(user_type='admin', is_active=True).first()
            if admin:
                notification = Notification(
                    user_id=admin.id,
                    title='Artisan Verification Request',
                    message=f'Artisan {current_user.full_name} has requested account verification',
                    notification_type='verification_request',
                    related_id=current_user.id
                )
                db.session.add(notification)
            
            db.session.commit()
            
            return jsonify({'message': 'Verification request submitted successfully'})
        
        elif action == 'upload-portfolio-image':
            # Handle file upload for portfolio images
            if 'portfolio_image' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400
            
            file = request.files['portfolio_image']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
            
            # Validate file type
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
                return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP'}), 400
            
            # Save file
            filename = secure_filename(file.filename)
            file_path = os.path.join(
                current_app.config['UPLOAD_FOLDER'],
                'portfolio',
                filename
            )
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            
            # Update portfolio images
            portfolio_images = []
            if current_user.artisan_profile and current_user.artisan_profile.portfolio_images:
                portfolio_images = json.loads(current_user.artisan_profile.portfolio_images)
            
            # Add new image (limit to 20)
            portfolio_images.insert(0, f'portfolio/{filename}')
            portfolio_images = portfolio_images[:20]
            
            current_user.artisan_profile.portfolio_images = json.dumps(portfolio_images)
            current_user.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            return jsonify({
                'message': 'Image uploaded successfully',
                'image_url': f'portfolio/{filename}',
                'portfolio_images': portfolio_images
            })
        
        return jsonify({'error': 'Invalid action'}), 400

# Helper functions for profile statistics
def calculate_response_rate(artisan_id):
    """Calculate response rate to job assignments"""
    assigned_jobs = ServiceRequest.query.filter_by(
        artisan_id=artisan_id,
        status='assigned'
    ).count()
    
    accepted_jobs = ServiceRequest.query.filter(
        ServiceRequest.artisan_id == artisan_id,
        ServiceRequest.status.in_(['in_progress', 'completed'])
    ).count()
    
    if assigned_jobs == 0:
        return 100  # No assigned jobs means perfect response rate
    
    response_rate = (accepted_jobs / assigned_jobs) * 100
    return round(response_rate, 1)


def calculate_completion_rate(artisan_id):
    """Calculate job completion rate"""
    accepted_jobs = ServiceRequest.query.filter(
        ServiceRequest.artisan_id == artisan_id,
        ServiceRequest.status.in_(['in_progress', 'completed', 'cancelled'])
    ).count()
    
    completed_jobs = ServiceRequest.query.filter_by(
        artisan_id=artisan_id,
        status='completed'
    ).count()
    
    if accepted_jobs == 0:
        return 100  # No accepted jobs means perfect completion rate
    
    completion_rate = (completed_jobs / accepted_jobs) * 100
    return round(completion_rate, 1)

@artisan_bp.route('/portfolio', methods=['GET', 'POST'])
@artisan_required
def artisan_portfolio():
    """Handle portfolio management - view and upload images"""
    
    if request.method == 'GET':
        portfolio_images = get_portfolio_images(current_user)
        return render_template('artisan/portfolio.html',
                             portfolio_images=portfolio_images,
                             max_images=20)
    
    # POST - Handle file uploads
    if 'portfolio_images' not in request.files:
        flash('No files selected', 'danger')
        return redirect(url_for('artisan_bp.artisan_portfolio'))
    
    files = request.files.getlist('portfolio_images')
    if not files:
        flash('No files selected', 'danger')
        return redirect(url_for('artisan_bp.artisan_portfolio'))
    
    uploaded_urls = []
    errors = []
    
    # Check total images limit
    existing_images = get_portfolio_images(current_user)
    if len(existing_images) + len(files) > 20:
        flash(f'You can only have 20 images total. You have {len(existing_images)} currently.', 'warning')
    
    for file in files:
        if file and file.filename != '':
            # Validate file
            is_valid, error_msg = validate_file(file)
            if not is_valid:
                errors.append(f"{file.filename}: {error_msg}")
                continue
            
            try:
                # Save image based on environment
                if current_app.config.get('FLASK_ENV') == 'development':
                    image_url = save_image_locally(file, current_user.id)
                else:
                    image_url = upload_to_cloudinary(file, current_user.id)
                
                if image_url:
                    uploaded_urls.append(image_url)
                else:
                    errors.append(f"{file.filename}: Failed to save")
                    
            except Exception as e:
                errors.append(f"{file.filename}: Error")
                print(f"Upload error: {e}")
    
    # Process successful uploads
    if uploaded_urls:
        # Add new images at the beginning
        all_images = uploaded_urls + existing_images
        
        # Limit to 20 images
        if len(all_images) > 20:
            all_images = all_images[:20]
            flash('Portfolio limited to 20 images. Oldest images removed.', 'info')
        
        # Save to database
        try:
            current_user.portfolio_images = json.dumps(all_images)
            db.session.commit()
            flash(f'Successfully uploaded {len(uploaded_urls)} image(s)', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error saving to database', 'danger')
    
    # Show errors
    for error in errors[:5]:  # Show first 5 errors
        flash(error, 'warning')
    
    if not uploaded_urls and not errors:
        flash('No valid images uploaded', 'warning')
    
    return redirect(url_for('artisan_bp.artisan_portfolio'))


@artisan_bp.route('/portfolio/delete', methods=['POST'])
@artisan_required
def delete_portfolio_image():
    """Delete a portfolio image from Cloudinary and database"""
    try:
        public_id = request.form.get('public_id')
        
        if not public_id:
            flash('No image specified', 'danger')
            return redirect(url_for('artisan_bp.artisan_portfolio'))
        
        # Get current portfolio
        portfolio_images = get_portfolio_images(current_user)
        
        # Find and remove the image
        image_to_remove = None
        updated_portfolio = []
        
        for img in portfolio_images:
            if img.get('public_id') == public_id:
                image_to_remove = img
            else:
                updated_portfolio.append(img)
        
        if image_to_remove:
            try:
                # Delete from Cloudinary
                cloudinary.uploader.destroy(
                    image_to_remove['public_id'],
                    resource_type="image"
                )
                current_app.logger.info(f"Deleted image from Cloudinary: {public_id}")
            except Exception as e:
                current_app.logger.error(f"Cloudinary delete error: {str(e)}")
                # Continue anyway - we'll remove from our DB
            
            # Update database
            if save_portfolio_images(current_user, updated_portfolio):
                flash('Image removed from portfolio', 'success')
            else:
                flash('Error updating portfolio', 'danger')
        else:
            flash('Image not found in portfolio', 'warning')
            
    except Exception as e:
        current_app.logger.error(f"Delete error: {str(e)}")
        flash('Error removing image', 'danger')
    
    return redirect(url_for('artisan_bp.artisan_portfolio'))


@artisan_bp.route('/portfolio/reorder', methods=['POST'])
@artisan_required
def reorder_portfolio_images():
    """Reorder portfolio images"""
    try:
        order = request.json.get('order', [])
        if not order:
            return jsonify({'success': False, 'error': 'No order provided'}), 400
        
        # Validate order contains only public_ids from user's portfolio
        portfolio_images = get_portfolio_images(current_user)
        portfolio_dict = {img.get('public_id'): img for img in portfolio_images}
        
        # Reorder based on provided order
        reordered_images = []
        for public_id in order:
            if public_id in portfolio_dict:
                reordered_images.append(portfolio_dict[public_id])
        
        # Add any missing images (shouldn't happen but safety)
        for img in portfolio_images:
            if img.get('public_id') not in order:
                reordered_images.append(img)
        
        # Save reordered portfolio
        if save_portfolio_images(current_user, reordered_images):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Database error'}), 500
            
    except Exception as e:
        current_app.logger.error(f"Reorder error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
    
@artisan_bp.route('/portfolio/featured', methods=['POST'])
@artisan_required
def set_featured_image():
    """Set an image as featured (move to first position)"""
    try:
        public_id = request.form.get('public_id')
        
        if not public_id:
            return jsonify({'success': False, 'error': 'No image specified'})
        
        portfolio_images = get_portfolio_images(current_user)
        
        # Find the image
        image_to_feature = None
        other_images = []
        
        for img in portfolio_images:
            if img.get('public_id') == public_id:
                image_to_feature = img
            else:
                other_images.append(img)
        
        if image_to_feature:
            # Move to first position
            new_portfolio = [image_to_feature] + other_images
            
            if save_portfolio_images(current_user, new_portfolio):
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Database error'})
        else:
            return jsonify({'success': False, 'error': 'Image not found'})
            
    except Exception as e:
        current_app.logger.error(f"Set featured error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
    
# Add a route to serve portfolio images
@artisan_bp.route('/portfolio/image/<path:filename>')
def serve_portfolio_image(filename):
    from flask import send_from_directory
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'portfolio'), filename)


# Job Management
@artisan_bp.route('/jobs', methods=['GET'])
@artisan_required
def assigned_jobs():
    status = request.args.get('status')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')
    
    # Base query
    query = ServiceRequest.query.filter_by(artisan_id=current_user.id)
    
    # Apply status filter
    if status:
        query = query.filter_by(status=status)
    
    # Apply sorting
    if sort_by == 'created_at':
        if sort_order == 'asc':
            query = query.order_by(ServiceRequest.created_at.asc())
        else:
            query = query.order_by(ServiceRequest.created_at.desc())
    elif sort_by == 'price':
        if sort_order == 'asc':
            query = query.order_by(ServiceRequest.actual_price.asc())
        else:
            query = query.order_by(ServiceRequest.actual_price.desc())
    elif sort_by == 'title':
        if sort_order == 'asc':
            query = query.order_by(ServiceRequest.title.asc())
        else:
            query = query.order_by(ServiceRequest.title.desc())
    
    # Get paginated jobs
    paginated_jobs = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Calculate statistics
    stats = {
        'assigned_jobs': ServiceRequest.query.filter_by(
            artisan_id=current_user.id,
            status='assigned'
        ).count(),
        'active_jobs': ServiceRequest.query.filter_by(
            artisan_id=current_user.id,
            status='in_progress'
        ).count(),
        'completed_jobs': ServiceRequest.query.filter_by(
            artisan_id=current_user.id,
            status='completed'
        ).count(),
        'cancelled_jobs': ServiceRequest.query.filter_by(
            artisan_id=current_user.id,
            status='cancelled'
        ).count(),
        'total_jobs': ServiceRequest.query.filter_by(
            artisan_id=current_user.id
        ).count(),
    }
    
    # Calculate average completion time for completed jobs
    completed_jobs = ServiceRequest.query.filter_by(
        artisan_id=current_user.id,
        status='completed'
    ).all()
    
    avg_completion_time = None
    if completed_jobs:
        total_days = 0
        for job in completed_jobs:
            if job.created_at and job.updated_at:
                days = (job.updated_at - job.created_at).days
                total_days += days
        avg_completion_time = total_days / len(completed_jobs)
    
    # Get jobs by category for chart
    jobs_by_category = {}
    all_jobs = ServiceRequest.query.filter_by(artisan_id=current_user.id).all()
    for job in all_jobs:
        category = job.category.name if job.category else 'Uncategorized'
        jobs_by_category[category] = jobs_by_category.get(category, 0) + 1
    
    if request.is_json:
        return jsonify({
            'jobs': [job.to_dict() for job in paginated_jobs.items],
            'stats': stats,
            'avg_completion_time': avg_completion_time,
            'jobs_by_category': jobs_by_category,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated_jobs.total,
                'pages': paginated_jobs.pages
            }
        })
    else:
        return render_template('artisan/jobs.html',
                              jobs=paginated_jobs.items,
                              stats=stats,
                              avg_completion_time=avg_completion_time,
                              jobs_by_category=jobs_by_category,
                              status_filter=status,
                              sort_by=sort_by,
                              sort_order=sort_order,
                              pagination=paginated_jobs,
                              page=page)
    
@artisan_bp.route('/job/<job_id>', methods=['GET'])
@artisan_required
def view_job(job_id):
    job = ServiceRequest.query.get_or_404(job_id)
    
    # Ensure artisan is assigned to this job
    if job.artisan_id != current_user.id:
        if request.is_json:
            return jsonify({'error': 'Unauthorized'}), 403
        else:
            return render_template('error.html', message='Unauthorized access'), 403
    
    if request.is_json:
        return jsonify(job.to_dict())
    else:
        return render_template('artisan/view_job.html', job=job)

@artisan_bp.route('/job/<job_id>/accept', methods=['PUT', 'POST'])
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
        title='Job Accepted by Artisan',
        message=f'Artisan {current_user.full_name} has accepted job: {job.title}',
        notification_type='job_accepted',
        related_id=job_id
    )
    db.session.add(notification)
    db.session.commit()
    
    if request.method == 'POST' and not request.is_json:
        return redirect(url_for('artisan_bp.view_job', job_id=job_id))
    
    return jsonify({'message': 'Job accepted successfully'})

@artisan_bp.route('/job/<job_id>/complete', methods=['PUT', 'POST'])
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
        title='Job Completed',
        message=f'Job {job.title} has been completed by {current_user.full_name}',
        notification_type='job_completed',
        related_id=job_id
    )
    
    # Create notification for user
    user_notification = Notification(
        user_id=job.user_id,
        title='Service Completed',
        message=f'Your service request has been completed by {current_user.full_name}',
        notification_type='service_completed',
        related_id=job_id
    )
    
    db.session.add(admin_notification)
    db.session.add(user_notification)
    db.session.commit()
    
    if request.method == 'POST' and not request.is_json:
        return redirect(url_for('artisan_bp.view_job', job_id=job_id))
    
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
def earnings():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # Base query for completed jobs
    query = ServiceRequest.query.filter_by(
        artisan_id=current_user.id,
        status='completed'
    )
    
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            # Convert to UTC if your database stores UTC
            start = start.replace(tzinfo=timezone.utc)
            query = query.filter(ServiceRequest.created_at >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            # Convert to UTC and set to end of day
            end = end.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            query = query.filter(ServiceRequest.created_at <= end)
        except ValueError:
            pass
    
    # Get statistics - FIXED: Use proper aggregation
    total_completed_jobs = query.count()
    
    # Total earnings from completed jobs
    total_earnings_result = db.session.query(db.func.coalesce(db.func.sum(ServiceRequest.actual_price), 0))\
        .filter(ServiceRequest.artisan_id == current_user.id,
                ServiceRequest.status == 'completed',
                ServiceRequest.actual_price.isnot(None))\
        .scalar()
    total_earnings = float(total_earnings_result) if total_earnings_result else 0.0
    
    # This month's earnings
    today = datetime.now(timezone.utc)
    first_day_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_earnings_result = db.session.query(db.func.coalesce(db.func.sum(ServiceRequest.actual_price), 0))\
        .filter(ServiceRequest.artisan_id == current_user.id,
                ServiceRequest.status == 'completed',
                ServiceRequest.actual_price.isnot(None),
                ServiceRequest.created_at >= first_day_of_month)\
        .scalar()
    monthly_earnings = float(monthly_earnings_result) if monthly_earnings_result else 0.0
    
    # Last month's earnings - FIXED: Proper date calculation
    first_day_this_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_last_month = first_day_this_month - timedelta(days=1)
    first_day_last_month = last_day_last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    last_month_earnings_result = db.session.query(db.func.coalesce(db.func.sum(ServiceRequest.actual_price), 0))\
        .filter(ServiceRequest.artisan_id == current_user.id,
                ServiceRequest.status == 'completed',
                ServiceRequest.actual_price.isnot(None),
                ServiceRequest.created_at >= first_day_last_month,
                ServiceRequest.created_at <= last_day_last_month)\
        .scalar()
    last_month_earnings = float(last_month_earnings_result) if last_month_earnings_result else 0.0
    
    # Get paginated jobs
    paginated_jobs = query.order_by(ServiceRequest.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    # Generate earnings data for chart (last 6 months) - FIXED
    earnings_values = []
    labels = []
    for i in range(5, -1, -1):
        # Calculate month start and end properly
        month_start = (first_day_this_month - timedelta(days=30*i))
        # Find last day of the month
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
        
        # Set time to end of day
        month_end = month_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        month_earnings_result = db.session.query(db.func.coalesce(db.func.sum(ServiceRequest.actual_price), 0))\
            .filter(ServiceRequest.artisan_id == current_user.id,
                    ServiceRequest.status == 'completed',
                    ServiceRequest.actual_price.isnot(None),
                    ServiceRequest.created_at >= month_start,
                    ServiceRequest.created_at <= month_end)\
            .scalar()
        month_earnings = float(month_earnings_result) if month_earnings_result else 0.0
        
        earnings_values.append(month_earnings)
        labels.append(month_start.strftime('%b %Y'))
    
    # Get transaction history - FIXED: Use actual data
    transactions = []
    
    # Add completed jobs as transactions
    for job in paginated_jobs.items:
        if job.actual_price:
            transactions.append({
                'id': job.id,
                'type': 'credit',
                'amount': float(job.actual_price),
                'description': f'Payment for job: {job.title}',
                'date': job.created_at,
                'status': 'paid',
                'job_id': job.id
            })
    
    # Get actual withdrawals from Withdrawal model
    withdrawals = Withdrawal.query.filter_by(artisan_id=current_user.id).all()
    for withdrawal in withdrawals:
        transactions.append({
            'id': withdrawal.id,
            'type': 'debit',
            'amount': float(withdrawal.amount),
            'description': f'Withdrawal - {withdrawal.method}',
            'date': withdrawal.requested_at,
            'status': withdrawal.status,
            'notes': withdrawal.account_details
        })
    
    # Get payment transactions
    payments = PaymentTransaction.query.filter_by(user_id=current_user.id).all()
    for payment in payments:
        transactions.append({
            'id': payment.id,
            'type': 'payment' if payment.transaction_status == 'completed' else 'pending',
            'amount': float(payment.amount),
            'description': f'Payment - {payment.payment_method}',
            'date': payment.created_at,
            'status': payment.transaction_status,
            'reference': payment.transaction_reference
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'], reverse=True)
    
    # Calculate average rating - FIXED: Get from reviews
    reviews = Review.query.filter_by(reviewee_id=current_user.id).all()
    if reviews:
        average_rating = sum(review.rating for review in reviews) / len(reviews)
    else:
        average_rating = 0.0
    
    # Calculate success rate - FIXED
    total_assigned_jobs = ServiceRequest.query.filter_by(
        artisan_id=current_user.id
    ).count()
    success_rate = (total_completed_jobs / total_assigned_jobs * 100) if total_assigned_jobs > 0 else 0.0
    
    # Get actual withdrawal totals
    total_withdrawals_result = db.session.query(db.func.coalesce(db.func.sum(Withdrawal.amount), 0))\
        .filter(Withdrawal.artisan_id == current_user.id,
                Withdrawal.status == 'completed')\
        .scalar()
    total_withdrawals = float(total_withdrawals_result) if total_withdrawals_result else 0.0
    
    pending_withdrawals_result = db.session.query(db.func.coalesce(db.func.sum(Withdrawal.amount), 0))\
        .filter(Withdrawal.artisan_id == current_user.id,
                Withdrawal.status == 'pending')\
        .scalar()
    pending_withdrawals = float(pending_withdrawals_result) if pending_withdrawals_result else 0.0
    
    # Calculate available balance (total earnings - completed withdrawals)
    available_balance = total_earnings - total_withdrawals
    
    # Calculate pending balance (for pending withdrawals)
    pending_balance = pending_withdrawals
    
    # If artisan has artisan_profile, use its financial fields
    if current_user.artisan_profile:
        current_user.artisan_profile.total_earnings = total_earnings
        current_user.artisan_profile.available_balance = available_balance
        current_user.artisan_profile.pending_balance = pending_balance
        db.session.commit()
    
    stats = {
        'total_earnings': round(total_earnings, 2),
        'monthly_earnings': round(monthly_earnings, 2),
        'last_month_earnings': round(last_month_earnings, 2),
        'completed_jobs': total_completed_jobs,
        'average_rating': round(average_rating, 1),
        'success_rate': round(success_rate, 1),
        'available_balance': round(available_balance, 2),
        'total_withdrawals': round(total_withdrawals, 2),
        'pending_withdrawals': round(pending_withdrawals, 2),
        'pending_balance': round(pending_balance, 2),
        'total_jobs': total_assigned_jobs
    }
    
    if request.is_json:
        return jsonify({
            'stats': stats,
            'transactions': transactions[:per_page],
            'earnings_data': {
                'labels': labels,
                'values': earnings_values
            },
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated_jobs.total,
                'pages': paginated_jobs.pages
            }
        })
    else:
        return render_template('artisan/earnings.html',
                              stats=stats,
                              transactions=transactions[:20],
                              earnings_data={
                                  'labels': labels,
                                  'values': earnings_values
                              },
                              jobs=paginated_jobs.items,
                              pagination=paginated_jobs,
                              start_date=start_date,
                              end_date=end_date,
                              page=page)
        
# Notifications
@artisan_bp.route('/notifications', methods=['GET'])
@artisan_required
def artisan_notifications():
    filter_type = request.args.get('filter', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Base query
    query = Notification.query.filter_by(
        user_id=current_user.id
    )
    
    # Apply filters
    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'job':
        query = query.filter(Notification.notification_type.contains('job'))
    elif filter_type == 'payment':
        query = query.filter(Notification.notification_type.contains('payment'))
    elif filter_type == 'system':
        query = query.filter(Notification.notification_type.contains('system'))
    
    # Get counts for stats
    total_count = Notification.query.filter_by(
        user_id=current_user.id
    ).count()
    
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    # This month's notifications
    today = datetime.now()
    first_day_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_count = Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.created_at >= first_day_of_month
    ).count()
    
    # Get paginated notifications
    paginated_notifications = query.order_by(
        Notification.created_at.desc(),
        Notification.is_read.asc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    # Get notification preferences
    notification_preferences = {
        'email_notifications': True,
        'job_alerts': True,
        'payment_alerts': True,
        'system_updates': True,
        'new_job_notifications': True,
        'job_updates': True,
        'payment_notifications': True,
        'rating_notifications': True,
        'system_announcements': True,
        'marketing_emails': False
    }
    
    if request.is_json:
        return jsonify({
            'notifications': [n.to_dict() for n in paginated_notifications.items],
            'stats': {
                'total_count': total_count,
                'unread_count': unread_count,
                'this_month_count': this_month_count
            },
            'preferences': notification_preferences,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated_notifications.total,
                'pages': paginated_notifications.pages,
                'has_more': paginated_notifications.has_next
            }
        })
    else:
        return render_template('artisan/notifications.html',
                              notifications=paginated_notifications.items,
                              total_count=total_count,
                              unread_count=unread_count,
                              this_month_count=this_month_count,
                              filter_type=filter_type,
                              pagination=paginated_notifications,
                              page=page,
                              total_pages=paginated_notifications.pages,
                              has_more=paginated_notifications.has_next,
                              preferences=notification_preferences)

@artisan_bp.route('/notifications/<notification_id>/read', methods=['PUT', 'POST'])
@artisan_required
def mark_artisan_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    notification.is_read = True
    db.session.commit()
    
    if request.method == 'POST' and not request.is_json:
        return redirect(url_for('artisan_bp.artisan_notifications'))
    
    return jsonify({'message': 'Notification marked as read'})


@artisan_bp.route('/notifications/mark-all-read', methods=['POST'])
@artisan_required
def mark_all_notifications_read():
    updated = Notification.query.filter_by(
        user_id=current_user.id,
        user_type='artisan',
        is_read=False
    ).update({'is_read': True})
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Marked {updated} notifications as read'
    })


@artisan_bp.route('/notifications/delete/<notification_id>', methods=['DELETE'])
@artisan_required
def delete_notification(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Notification deleted'})


@artisan_bp.route('/notifications/delete-all-read', methods=['DELETE'])
@artisan_required
def delete_all_read_notifications():
    deleted = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=True
    ).delete()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': f'Deleted {deleted} read notifications'
    })


@artisan_bp.route('/notifications/preferences', methods=['POST'])
@artisan_required
def update_notification_preferences():
    data = request.get_json()
    
    # Here you would save preferences to a UserSettings model
    # For now, we'll just acknowledge the request
    
    # Example: Save to database
    # user_settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    # if not user_settings:
    #     user_settings = UserSettings(user_id=current_user.id)
    #     db.session.add(user_settings)
    # 
    # user_settings.notification_preferences = json.dumps(data)
    # db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Notification preferences updated'
    })

# Service Categories
@artisan_bp.route('/categories', methods=['GET'])
def get_service_categories():
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    return jsonify({'categories': [cat.to_dict() for cat in categories]})