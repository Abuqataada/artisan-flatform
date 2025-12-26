from flask import Flask, render_template
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

login_manager = LoginManager()
migrate = Migrate()

def create_app(config_class=Config):
    app.config['UPLOAD_FOLDER'] = 'static/uploads'
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

    # Create upload directories if they don't exist
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'portfolio'), exist_ok=True)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Configure login manager
    login_manager.login_view = 'user_bp.login'
    login_manager.login_message_category = 'info'
    
    # Custom Jinja2 filters
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

app = create_app()

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