from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from functools import wraps
from models import db, Artisan, ServiceRequest, ServiceCategory, Notification
from datetime import datetime, timedelta
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

def validate_image_file(file):
    """Comprehensive validation for image files"""
    if not file or file.filename == '':
        return False, "No file selected"
    
    if not allowed_file(file.filename):
        return False, f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)
    
    if file_length == 0:
        return False, "File is empty"
    
    if file_length > MAX_FILE_SIZE:
        size_mb = file_length / (1024 * 1024)
        return False, f"File too large ({size_mb:.1f}MB). Max: {MAX_FILE_SIZE/(1024*1024)}MB"
    
    return True, "Valid"

def upload_to_cloudinary(file, artisan_id):
    """Upload file to Cloudinary with optimized settings"""
    try:
        # Generate unique filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S%f')[:-3]
        original_name = secure_filename(file.filename)
        name_without_ext = os.path.splitext(original_name)[0]
        
        # Create unique public ID
        public_id = f"{artisan_id}_{timestamp}_{name_without_ext}"
        
        # Upload to Cloudinary with optimization
        result = cloudinary.uploader.upload(
            file,
            public_id=public_id,
            folder=f"artisans/{artisan_id}/portfolio",
            use_filename=False,  # Use our generated public_id
            unique_filename=True,
            overwrite=False,
            resource_type="auto",
            transformation=[
                {'width': 1200, 'crop': 'limit'},  # Responsive sizing
                {'quality': 'auto:good'},          # Auto quality
                {'fetch_format': 'auto'}           # Auto format
            ],
            tags=[f"artisan_{artisan_id}", "portfolio"]
        )
        
        # Return secure URL
        return {
            'url': result.get('secure_url'),
            'public_id': result.get('public_id'),
            'format': result.get('format'),
            'bytes': result.get('bytes'),
            'created_at': result.get('created_at')
        }
        
    except cloudinary.exceptions.Error as e:
        current_app.logger.error(f"Cloudinary upload error: {str(e)}")
        return None
    except Exception as e:
        current_app.logger.error(f"Unexpected upload error: {str(e)}")
        return None

def get_portfolio_images(user):
    """Safely retrieve portfolio images from user"""
    try:
        if user.portfolio_images:
            return json.loads(user.portfolio_images)
    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        current_app.logger.warning(f"Error parsing portfolio images: {str(e)}")
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
        if not isinstance(current_user, Artisan):
            if request.is_json:
                return jsonify({'error': 'Artisan access required'}), 403
            else:
                return render_template('error.html', message='Artisan access required'), 403
        return f(*args, **kwargs)
    return decorated

# Registration and Profile
@artisan_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('auth/artisan_register.html')
    
    elif request.method == 'POST':
        data = request.form if request.form else request.get_json()
        
        # Check if artisan already exists
        if Artisan.query.filter_by(email=data.get('email')).first():
            if request.is_json:
                return jsonify({'error': 'Email already registered'}), 400
            else:
                return render_template('auth/artisan_register.html', 
                                      error='Email already registered')
        
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
        
        if request.is_json:
            return jsonify({
                'message': 'Registration submitted for verification',
                'artisan': artisan.to_dict()
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
        user_id=current_user.id,
        user_type='artisan'
    ).order_by(Notification.created_at.desc())\
     .limit(5)\
     .all()
    
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        user_type='artisan',
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

@artisan_bp.route('/profile', methods=['GET', 'PUT', 'POST'])
@artisan_required
def artisan_profile():
    if request.method == 'GET':
        # Calculate profile completion percentage
        profile_fields = [
            ('full_name', current_user.full_name),
            ('email', current_user.email),
            ('phone', current_user.phone),
            ('category', current_user.category),
            ('skills', current_user.skills),
            ('experience_years', current_user.experience_years),
            ('portfolio_images', current_user.portfolio_images),
            ('credentials', current_user.credentials),
        ]
        
        completed_fields = sum(1 for field, value in profile_fields if value)
        total_fields = len(profile_fields)
        profile_completion = int((completed_fields / total_fields) * 100)
        
        # Get categories for dropdown
        from models import ServiceCategory
        categories = ServiceCategory.query.filter_by(is_active=True).all()
        
        # Get statistics for profile page
        stats = {
            'completed_jobs': ServiceRequest.query.filter_by(
                artisan_id=current_user.id,
                status='completed'
            ).count(),
            'total_earnings': db.session.query(db.func.sum(ServiceRequest.actual_price))
                .filter(ServiceRequest.artisan_id == current_user.id,
                        ServiceRequest.status == 'completed',
                        ServiceRequest.actual_price.isnot(None))
                .scalar() or 0,
            'active_jobs': ServiceRequest.query.filter_by(
                artisan_id=current_user.id,
                status='in_progress'
            ).count(),
            'pending_jobs': ServiceRequest.query.filter_by(
                artisan_id=current_user.id,
                status='assigned'
            ).count(),
            'average_rating': current_user.rating or 0,
            'response_rate': calculate_response_rate(current_user.id),
            'completion_rate': calculate_completion_rate(current_user.id),
        }
        
        if request.is_json:
            artisan_data = current_user.to_dict()
            artisan_data['credentials'] = json.loads(current_user.credentials) if current_user.credentials else []
            artisan_data['portfolio_images'] = json.loads(current_user.portfolio_images) if current_user.portfolio_images else []
            return jsonify({
                'artisan': artisan_data,
                'profile_completion': profile_completion,
                'stats': stats,
                'categories': [cat.to_dict() for cat in categories]
            })
        else:
            return render_template('artisan/profile.html',
                                  artisan=current_user,
                                  profile_completion=profile_completion,
                                  stats=stats,
                                  categories=categories)
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        # Update editable fields with validation
        editable_fields = ['phone', 'full_name', 'category', 'skills', 
                          'experience_years', 'availability']
        
        for field in editable_fields:
            if field in data:
                # Add validation based on field type
                if field == 'phone':
                    # Validate phone number
                    if not re.match(r'^\+?[\d\s\-\(\)]{10,}$', str(data[field])):
                        return jsonify({'error': 'Invalid phone number format'}), 400
                elif field == 'email':
                    # Check if email is already taken by another user
                    existing = Artisan.query.filter(
                        Artisan.email == data[field],
                        Artisan.id != current_user.id
                    ).first()
                    if existing:
                        return jsonify({'error': 'Email already registered'}), 400
                elif field == 'experience_years':
                    # Ensure it's a positive number
                    try:
                        years = int(data[field])
                        if years < 0 or years > 50:
                            return jsonify({'error': 'Experience years must be between 0 and 50'}), 400
                    except ValueError:
                        return jsonify({'error': 'Invalid experience years'}), 400
                
                setattr(current_user, field, data[field])
        
        # Handle credentials update
        if 'credentials' in data:
            if isinstance(data['credentials'], list):
                current_user.credentials = json.dumps(data['credentials'])
            else:
                current_user.credentials = data['credentials']
        
        # Handle portfolio images update
        if 'portfolio_images' in data:
            if isinstance(data['portfolio_images'], list):
                # Limit to 20 images
                images = data['portfolio_images'][:20]
                current_user.portfolio_images = json.dumps(images)
            else:
                current_user.portfolio_images = data['portfolio_images']
        
        # Update timestamp
        current_user.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'artisan': current_user.to_dict()
        })
    
    elif request.method == 'POST':
        # Handle specific POST actions like changing password, deactivating account, etc.
        action = request.args.get('action')
        
        if action == 'change-password':
            data = request.get_json()
            current_password = data.get('current_password')
            new_password = data.get('new_password')
            
            if not current_user.check_password(current_password):
                return jsonify({'error': 'Current password is incorrect'}), 400
            
            if len(new_password) < 8:
                return jsonify({'error': 'New password must be at least 8 characters long'}), 400
            
            current_user.set_password(new_password)
            db.session.commit()
            
            return jsonify({'message': 'Password changed successfully'})
        
        elif action == 'deactivate':
            data = request.get_json()
            reason = data.get('reason', '')
            
            # Create deactivation record
            from ..models import AccountDeactivation
            deactivation = AccountDeactivation(
                user_id=current_user.id,
                user_type='artisan',
                reason=reason
            )
            db.session.add(deactivation)
            
            # Deactivate account
            current_user.is_active = False
            db.session.commit()
            
            return jsonify({'message': 'Account deactivated successfully'})
        
        elif action == 'request-verification':
            # Check if already verified
            if current_user.is_verified:
                return jsonify({'error': 'Account is already verified'}), 400
            
            # Check if verification was recently requested
            from ..models import VerificationRequest
            recent_request = VerificationRequest.query.filter_by(
                user_id=current_user.id,
                user_type='artisan',
                status='pending'
            ).filter(
                VerificationRequest.created_at >= datetime.utcnow() - timedelta(days=7)
            ).first()
            
            if recent_request:
                return jsonify({'error': 'Verification request already pending. Please wait 7 days.'}), 400
            
            # Create verification request
            verification_request = VerificationRequest(
                user_id=current_user.id,
                user_type='artisan',
                status='pending',
                request_data=json.dumps({
                    'full_name': current_user.full_name,
                    'category': current_user.category,
                    'experience_years': current_user.experience_years,
                    'skills': current_user.skills,
                    'credentials': current_user.credentials
                })
            )
            db.session.add(verification_request)
            
            # Create notification for admin
            notification = Notification(
                user_id='admin',
                user_type='admin',
                title='Verification Request',
                message=f'Artisan {current_user.full_name} has requested account verification',
                notification_type='verification_request',
                related_id=current_user.id
            )
            db.session.add(notification)
            
            db.session.commit()
            
            return jsonify({'message': 'Verification request submitted successfully'})
        
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
        try:
            portfolio_images = get_portfolio_images(current_user)
            return render_template('artisan/portfolio.html',
                                 portfolio_images=portfolio_images,
                                 max_images=MAX_PORTFOLIO_IMAGES)
        except Exception as e:
            current_app.logger.error(f"Error loading portfolio: {str(e)}")
            flash('Error loading portfolio', 'danger')
            return render_template('artisan/portfolio.html', portfolio_images=[])
    
    # POST - Handle file uploads
    if 'portfolio_images' not in request.files:
        flash('No files selected', 'danger')
        return redirect(url_for('artisan_bp.artisan_portfolio'))
    
    files = request.files.getlist('portfolio_images')
    if not files or len(files) == 0:
        flash('No files selected', 'danger')
        return redirect(url_for('artisan_bp.artisan_portfolio'))
    
    uploaded_images = []
    errors = []
    successful_uploads = 0
    
    # Check total files being uploaded
    existing_count = len(get_portfolio_images(current_user))
    if existing_count + len(files) > MAX_PORTFOLIO_IMAGES:
        flash(f'You can only have {MAX_PORTFOLIO_IMAGES} images total. '
              f'You have {existing_count} images currently.', 'warning')
        # Allow upload but will trim later
    
    for index, file in enumerate(files):
        if file and file.filename != '':
            # Validate file
            is_valid, error_msg = validate_image_file(file)
            if not is_valid:
                errors.append(f"{file.filename}: {error_msg}")
                continue
            
            try:
                # Upload to Cloudinary
                upload_result = upload_to_cloudinary(file, current_user.id)
                
                if upload_result and upload_result.get('url'):
                    uploaded_images.append({
                        'url': upload_result['url'],
                        'public_id': upload_result.get('public_id'),
                        'uploaded_at': datetime.utcnow().isoformat()
                    })
                    successful_uploads += 1
                else:
                    errors.append(f"{file.filename}: Upload failed")
                    
            except Exception as e:
                current_app.logger.error(f"Upload error for {file.filename}: {str(e)}")
                errors.append(f"{file.filename}: Upload error")
    
    # Process successful uploads
    if successful_uploads > 0:
        try:
            # Get existing images
            existing_images = get_portfolio_images(current_user)
            
            # Add new images at the beginning (newest first)
            new_portfolio = uploaded_images + existing_images
            
            # Limit total images
            if len(new_portfolio) > MAX_PORTFOLIO_IMAGES:
                removed_count = len(new_portfolio) - MAX_PORTFOLIO_IMAGES
                new_portfolio = new_portfolio[:MAX_PORTFOLIO_IMAGES]
                flash(f'Portfolio limited to {MAX_PORTFOLIO_IMAGES} images. '
                      f'{removed_count} oldest image(s) removed.', 'info')
            
            # Save to database
            if save_portfolio_images(current_user, new_portfolio):
                flash(f'Successfully uploaded {successful_uploads} image(s)', 'success')
            else:
                flash('Error saving portfolio to database', 'danger')
                # Note: Images are already uploaded to Cloudinary but not linked
                
        except Exception as e:
            current_app.logger.error(f"Error updating portfolio: {str(e)}")
            flash('Error updating portfolio', 'danger')
    
    # Display errors
    if errors:
        error_count = len(errors)
        if error_count <= 3:
            for error in errors:
                flash(error, 'warning')
        else:
            flash(f'{error_count} files had errors. First few: {", ".join(errors[:3])}', 'warning')
    
    elif successful_uploads == 0:
        flash('No images were uploaded successfully', 'warning')
    
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
        user_type='admin',
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
            query = query.filter(ServiceRequest.created_at >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d')
            query = query.filter(ServiceRequest.created_at <= end)
        except ValueError:
            pass
    
    # Get statistics
    total_completed_jobs = query.count()
    total_earnings = db.session.query(db.func.sum(ServiceRequest.actual_price))\
        .filter(ServiceRequest.artisan_id == current_user.id,
                ServiceRequest.status == 'completed',
                ServiceRequest.actual_price.isnot(None))\
        .scalar() or 0
    
    # This month's earnings
    today = datetime.now()
    first_day_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_earnings = db.session.query(db.func.sum(ServiceRequest.actual_price))\
        .filter(ServiceRequest.artisan_id == current_user.id,
                ServiceRequest.status == 'completed',
                ServiceRequest.actual_price.isnot(None),
                ServiceRequest.created_at >= first_day_of_month)\
        .scalar() or 0
    
    # Last month's earnings
    last_month = today.replace(day=1) - timedelta(days=1)
    first_day_last_month = last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_earnings = db.session.query(db.func.sum(ServiceRequest.actual_price))\
        .filter(ServiceRequest.artisan_id == current_user.id,
                ServiceRequest.status == 'completed',
                ServiceRequest.actual_price.isnot(None),
                ServiceRequest.created_at >= first_day_last_month,
                ServiceRequest.created_at <= last_month)\
        .scalar() or 0
    
    # Get paginated jobs
    paginated_jobs = query.order_by(ServiceRequest.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    # Generate earnings data for chart (last 6 months)
    earnings_values = []
    labels = []
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=30*i))
        month_end = (month_start.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_earnings = db.session.query(db.func.sum(ServiceRequest.actual_price))\
            .filter(ServiceRequest.artisan_id == current_user.id,
                    ServiceRequest.status == 'completed',
                    ServiceRequest.actual_price.isnot(None),
                    ServiceRequest.created_at >= month_start,
                    ServiceRequest.created_at <= month_end)\
            .scalar() or 0
        
        earnings_values.append(float(month_earnings))
        labels.append(month_start.strftime('%b %Y'))
    
    # Get transaction history (including withdrawals, fees, etc.)
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
    
    # Add placeholder for withdrawals (you would fetch these from a Withdrawal model)
    withdrawals = []  # Replace with actual withdrawals query
    for withdrawal in withdrawals:
        transactions.append({
            'id': withdrawal.id,
            'type': 'debit',
            'amount': float(withdrawal.amount),
            'description': 'Withdrawal',
            'date': withdrawal.created_at,
            'status': withdrawal.status,
            'notes': f'Processed via {withdrawal.payment_method}'
        })
    
    # Sort transactions by date
    transactions.sort(key=lambda x: x['date'], reverse=True)
    
    # Calculate average rating
    average_rating = current_user.rating or 0
    
    # Calculate success rate
    total_assigned_jobs = ServiceRequest.query.filter_by(
        artisan_id=current_user.id
    ).count()
    success_rate = (total_completed_jobs / total_assigned_jobs * 100) if total_assigned_jobs > 0 else 0
    
    stats = {
        'total_earnings': float(total_earnings),
        'monthly_earnings': float(monthly_earnings),
        'last_month_earnings': float(last_month_earnings),
        'completed_jobs': total_completed_jobs,
        'average_rating': float(average_rating),
        'success_rate': round(success_rate, 1),
        'available_balance': float(total_earnings),  # In reality, subtract withdrawals
        'total_withdrawals': 0,  # Calculate from withdrawals table
        'pending_withdrawals': 0,
    }
    
    if request.is_json:
        return jsonify({
            'stats': stats,
            'transactions': transactions[:10],
            'earnings_data': {
                'labels': labels,
                'values': earnings_values  # Use earnings_values, not .values()
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
                                  'values': earnings_values  # Use earnings_values, not .values()
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
        user_id=current_user.id,
        user_type='artisan'
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
        user_id=current_user.id,
        user_type='artisan'
    ).count()
    
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        user_type='artisan',
        is_read=False
    ).count()
    
    # This month's notifications
    today = datetime.now()
    first_day_of_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    this_month_count = Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.user_type == 'artisan',
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
        user_type='artisan',
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