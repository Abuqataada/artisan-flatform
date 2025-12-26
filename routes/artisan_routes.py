from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
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

artisan_bp = Blueprint('artisan_bp', __name__)

# Add these configuration variables at the top of the file or in your config
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_portfolio_image(file, artisan_id):
    """Save uploaded image and return the filename"""
    if file and allowed_file(file.filename):
        # Generate unique filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{artisan_id}_{timestamp}_{filename}"
        
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'portfolio', artisan_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save the file
        filepath = os.path.join(upload_dir, unique_filename)
        
        # Optimize and resize image
        try:
            img = Image.open(file)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large (max 1200px width)
            max_width = 1200
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Save optimized image
            img.save(filepath, 'JPEG', quality=85, optimize=True)
            
            # Return relative path for database storage
            return os.path.join('portfolio', artisan_id, unique_filename)
            
        except Exception as e:
            print(f"Error processing image: {e}")
            return None
    
    return None


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
    if request.method == 'GET':
        # Get portfolio images from database
        portfolio_images = []
        if current_user.portfolio_images:
            try:
                portfolio_images = json.loads(current_user.portfolio_images)
            except:
                portfolio_images = []
        
        return render_template('artisan/portfolio.html', 
                              portfolio_images=portfolio_images)
    
    elif request.method == 'POST':
        # Handle portfolio image upload
        if 'portfolio_images' not in request.files:
            flash('No files selected', 'danger')
            return redirect(url_for('artisan_bp.artisan_portfolio'))
        
        files = request.files.getlist('portfolio_images')
        uploaded_files = []
        
        for file in files:
            if file and file.filename != '':
                # Check file size
                file.seek(0, os.SEEK_END)
                file_length = file.tell()
                file.seek(0)
                
                if file_length > MAX_FILE_SIZE:
                    flash(f'File {file.filename} is too large (max 16MB)', 'warning')
                    continue
                
                # Save the image
                saved_path = save_portfolio_image(file, current_user.id)
                if saved_path:
                    uploaded_files.append(saved_path)
        
        if uploaded_files:
            # Get existing images
            existing_images = []
            if current_user.portfolio_images:
                try:
                    existing_images = json.loads(current_user.portfolio_images)
                except:
                    existing_images = []
            
            # Add new images
            existing_images.extend(uploaded_files)
            
            # Limit to 20 images maximum
            if len(existing_images) > 20:
                existing_images = existing_images[-20:]
                flash('Portfolio limited to 20 images. Oldest images removed.', 'info')
            
            # Save to database
            current_user.portfolio_images = json.dumps(existing_images)
            db.session.commit()
            
            flash(f'Successfully uploaded {len(uploaded_files)} image(s)', 'success')
        else:
            flash('No valid images uploaded', 'warning')
        
        return redirect(url_for('artisan_bp.artisan_portfolio'))

@artisan_bp.route('/portfolio/delete', methods=['POST'])
@artisan_required
def delete_portfolio_image():
    data = request.get_json()
    image_path = data.get('image_path')
    
    if not image_path:
        return jsonify({'error': 'No image path provided'}), 400
    
    # Get current portfolio images
    portfolio_images = []
    if current_user.portfolio_images:
        try:
            portfolio_images = json.loads(current_user.portfolio_images)
        except:
            portfolio_images = []
    
    # Remove the image from the list
    if image_path in portfolio_images:
        portfolio_images.remove(image_path)
        
        # Try to delete the physical file
        try:
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], image_path)
            if os.path.exists(full_path):
                os.remove(full_path)
        except Exception as e:
            print(f"Error deleting file: {e}")
        
        # Update database
        current_user.portfolio_images = json.dumps(portfolio_images)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Image deleted'})
    
    return jsonify({'error': 'Image not found'}), 404

@artisan_bp.route('/portfolio/reorder', methods=['POST'])
@artisan_required
def reorder_portfolio_images():
    data = request.get_json()
    new_order = data.get('order', [])
    
    if not new_order:
        return jsonify({'error': 'No order provided'}), 400
    
    # Validate that all images belong to this artisan
    portfolio_images = []
    if current_user.portfolio_images:
        try:
            portfolio_images = json.loads(current_user.portfolio_images)
        except:
            portfolio_images = []
    
    # Check if all images in new order exist in current portfolio
    if not all(img in portfolio_images for img in new_order):
        return jsonify({'error': 'Invalid image list'}), 400
    
    # Update the order
    current_user.portfolio_images = json.dumps(new_order)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Portfolio order updated'})

@artisan_bp.route('/portfolio/set-featured', methods=['POST'])
@artisan_required
def set_featured_image():
    data = request.get_json()
    image_path = data.get('image_path')
    
    if not image_path:
        return jsonify({'error': 'No image path provided'}), 400
    
    # Get current portfolio images
    portfolio_images = []
    if current_user.portfolio_images:
        try:
            portfolio_images = json.loads(current_user.portfolio_images)
        except:
            portfolio_images = []
    
    # Check if image exists
    if image_path in portfolio_images:
        # Move image to first position (featured)
        portfolio_images.remove(image_path)
        portfolio_images.insert(0, image_path)
        
        # Update database
        current_user.portfolio_images = json.dumps(portfolio_images)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Featured image updated'})
    
    return jsonify({'error': 'Image not found'}), 404

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