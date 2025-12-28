from flask import Flask, render_template, url_for
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_cors import CORS
from config import Config
from models import db, User, Artisan, Admin, ServiceCategory
import os
from datetime import datetime, timedelta, timezone
from dateutil import tz
from dotenv import load_dotenv
from extension import app
import tempfile
from config import config


import cloudinary
import cloudinary.uploader


login_manager = LoginManager()
migrate = Migrate()


def populate_service_categories():
    """Replace ALL existing categories with the new simplified list"""
    
    # First, delete all existing categories
    deleted_count = ServiceCategory.query.delete()
    print(f"Deleted {deleted_count} existing categories")
    
    # Your exact list of categories
    categories = [
        'Barber',
        'Hair stylist',
        'Electrician',
        'Mechanic',
        'Plumber',
        'A.C installer',
        'DSTV installer',
        'Furniture installer',
        'Chef',
        'Cleaner',
        'Masseuse',
        'Nail Tech',
        'Braider',
        'Hair treater',
        'Nanny',
        'Care giver',
        'Makeup Artist',
        'Carpenter',
        'Solar installer',
        'Generator repairer',
        'Painter/Screeder',
        'Teacher'
    ]
    
    # Map categories to icons and descriptions
    category_details = {
        'Barber': {'icon': 'cut', 'desc': 'Professional hair cutting and grooming for men'},
        'Hair stylist': {'icon': 'user-tie', 'desc': 'Professional hair styling and treatment'},
        'Electrician': {'icon': 'bolt', 'desc': 'Electrical installations and repairs'},
        'Mechanic': {'icon': 'car', 'desc': 'Automobile repair and maintenance'},
        'Plumber': {'icon': 'faucet', 'desc': 'Plumbing installations and repairs'},
        'A.C installer': {'icon': 'snowflake', 'desc': 'Air conditioner installation'},
        'DSTV installer': {'icon': 'satellite-dish', 'desc': 'Satellite TV installation'},
        'Furniture installer': {'icon': 'couch', 'desc': 'Furniture assembly and installation'},
        'Chef': {'icon': 'utensils', 'desc': 'Professional cooking and catering'},
        'Cleaner': {'icon': 'broom', 'desc': 'Professional cleaning services'},
        'Masseuse': {'icon': 'spa', 'desc': 'Professional massage therapy'},
        'Nail Tech': {'icon': 'hand-sparkles', 'desc': 'Nail care and manicure services'},
        'Braider': {'icon': 'braid', 'desc': 'Professional hair braiding'},
        'Hair treater': {'icon': 'spray-can', 'desc': 'Hair treatment and care'},
        'Nanny': {'icon': 'baby', 'desc': 'Child care and babysitting'},
        'Care giver': {'icon': 'hands-helping', 'desc': 'Elderly and special needs care'},
        'Makeup Artist': {'icon': 'paint-brush', 'desc': 'Professional makeup application'},
        'Carpenter': {'icon': 'hammer', 'desc': 'Woodwork and carpentry'},
        'Solar installer': {'icon': 'solar-panel', 'desc': 'Solar panel installation'},
        'Generator repairer': {'icon': 'generator', 'desc': 'Generator maintenance and repair'},
        'Painter/Screeder': {'icon': 'paint-roller', 'desc': 'Painting and wall finishing'},
        'Teacher': {'icon': 'chalkboard-teacher', 'desc': 'Tutoring and educational services'}
    }
    
    # Add the new categories
    for category_name in categories:
        details = category_details.get(category_name, {'icon': 'tools', 'desc': 'Professional service'})
        
        category = ServiceCategory(
            name=category_name,
            description=details['desc'],
            icon=details['icon']
        )
        db.session.add(category)
    
    db.session.commit()
    
    print(f"Added {len(categories)} new categories:")
    for i, cat in enumerate(categories, 1):
        print(f"{i:2}. {cat}")
    
    return len(categories)



def create_app(config_class):
    # Load configuration FIRST
    app.config.from_object(config_class)
    
    # File upload configuration
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
    
    # Development: Use local storage
    if app.config.get('FLASK_ENV') == 'development':
        app.config['UPLOAD_FOLDER'] = 'static/uploads'
        app.config['USE_CLOUD_STORAGE'] = False
        
        # Create local directories
        try:
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'portfolio'), exist_ok=True)
        except OSError as e:
            print(f"Warning: Could not create upload directories: {e}")
    
    # Production: Use Cloudinary only
    else:
        app.config['USE_CLOUD_STORAGE'] = True
        
        # Initialize Cloudinary
        import cloudinary
        cloudinary.config(
            cloud_name=app.config['CLOUDINARY_CLOUD_NAME'],
            api_key=app.config['CLOUDINARY_API_KEY'],
            api_secret=app.config['CLOUDINARY_API_SECRET'],
            secure=True
        )
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Configure login manager
    login_manager.login_view = 'user_bp.login'
    login_manager.login_message_category = 'info'
    
    # Add context processor for helper functions
    @app.context_processor
    def utility_processor():
        def get_artisan_count(category_name):
            """Get count of artisans in a category"""
            from models import Artisan
            return Artisan.query.filter_by(category=category_name, is_active=True, is_verified=True).count()
        
        def get_average_rating(category_name):
            """Get average rating for a category"""
            from models import Artisan
            artisans = Artisan.query.filter_by(category=category_name, is_active=True, is_verified=True).all()
            if not artisans:
                return 4.5  # Default rating
            total_rating = sum(artisan.rating or 0 for artisan in artisans)
            avg = total_rating / len(artisans)
            return round(avg, 1)
        
        return dict(get_artisan_count=get_artisan_count, get_average_rating=get_average_rating)
    
    # Add context processor for helper function
    @app.context_processor
    def utility_processor():
        def get_notification_link(notification):
            """Get appropriate link for notification"""
            if notification.notification_type == 'new_request' and notification.related_id:
                return url_for('user_bp.view_request', request_id=notification.related_id)
            elif notification.notification_type == 'status_update' and notification.related_id:
                return url_for('user_bp.view_request', request_id=notification.related_id)
            elif notification.notification_type == 'artisan_assigned' and notification.related_id:
                return url_for('user_bp.view_request', request_id=notification.related_id)
            elif notification.notification_type == 'message' and notification.related_id:
                return '#'  # Would link to messages
            else:
                return '#'
        
        return dict(get_notification_link=get_notification_link)

    # Custom Jinja2 filters
    @app.template_filter('nl2br')
    def nl2br_filter(text):
        """Convert newlines to <br> tags for HTML display"""
        if not text:
            return ''
        return text.replace('\n', '<br>')

    @app.template_filter('number_format')
    def number_format_filter(value, decimals=2):
        """Format number with commas"""
        if value is None:
            return "0.00"
        return f"{value:,.{decimals}f}"

    @app.template_filter('yesno')
    def yesno_filter(value, yes='Yes', no='No'):
        """Convert boolean to Yes/No"""
        return yes if value else no

    @app.template_filter('relative_time')
    def relative_time_filter(dt):
        """Convert datetime to relative time string"""
        if not dt:
            return "Unknown time"
        
        # Convert both datetimes to UTC for comparison
        now = datetime.now(timezone.utc)
        
        # If dt is naive (no timezone), assume it's UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # If dt is aware, convert to UTC
        else:
            dt = dt.astimezone(timezone.utc)
        
        diff = now - dt
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    
    @app.template_filter('format_currency')
    def format_currency_filter(value):
        """Format currency with Naira symbol"""
        if value is None:
            return "₦0.00"
        return f"₦{value:,.2f}"
    
    @app.template_filter('format_date')
    def format_date_filter(dt, format='%b %d, %Y'):
        """Format datetime object"""
        if not dt:
            return ""
        return dt.strftime(format)
    
    @app.template_filter('format_datetime')
    def format_datetime_filter(dt):
        """Format datetime with time"""
        if not dt:
            return ""
        return dt.strftime('%b %d, %Y %I:%M %p')
    
    @app.template_filter('truncate')
    def truncate_filter(text, length=100):
        """Truncate text to specified length"""
        if not text:
            return ""
        if len(text) <= length:
            return text
        return text[:length] + "..."
    
    # Register the filters
    app.jinja_env.filters['relative_time'] = relative_time_filter
    app.jinja_env.filters['format_currency'] = format_currency_filter
    app.jinja_env.filters['format_date'] = format_date_filter
    app.jinja_env.filters['format_datetime'] = format_datetime_filter
    app.jinja_env.filters['truncate'] = truncate_filter
    app.jinja_env.filters['nl2br'] = nl2br_filter
    app.jinja_env.filters['number_format'] = number_format_filter
    app.jinja_env.filters['yesno'] = yesno_filter
    
    @login_manager.user_loader
    def load_user(user_id):
        # Try to load user from all user types
        user = User.query.get(user_id)
        if user:
            return user
        
        artisan = Artisan.query.get(user_id)
        if artisan:
            return artisan
            
        admin = Admin.query.get(user_id)
        if admin:
            return admin
            
        return None
    
    # Register blueprints
    from routes.user_routes import user_bp
    from routes.admin_routes import admin_bp
    from routes.artisan_routes import artisan_bp
    
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(artisan_bp, url_prefix='/artisan')
    
    # Create database tables
    with app.app_context():
        db.create_all()

        # Populate service categories if empty
        if ServiceCategory.query.count() == 0:
            populate_service_categories()
        
        # Create default admin if not exists
        if not Admin.query.filter_by(email='admin@uwailaglobal.com').first():
            default_admin = Admin(
                email='admin@uwailaglobal.com',
                username='admin',
                full_name='System Administrator'
            )
            default_admin.set_password('Admin123!')
            db.session.add(default_admin)
            db.session.commit()
    
    return app

load_dotenv()

# Determine the configuration based on environment
config_name = os.environ.get('FLASK_ENV', 'default')
if os.environ.get('SERVERLESS'):
    config_name = 'serverless'

app = create_app(config[config_name])

# Main routes
@app.route('/')
def index():
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    return render_template('index.html', categories=categories)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    categories = ServiceCategory.query.filter_by(is_active=True).all()
    return render_template('services.html', categories=categories)

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(port=port, debug=debug)