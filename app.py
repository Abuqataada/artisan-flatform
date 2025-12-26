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
import tempfile
from config import config


import cloudinary
import cloudinary.uploader


login_manager = LoginManager()
migrate = Migrate()

def populate_service_categories():
    """Populate database with categories matching the HTML form"""
    
    categories = [
        # 🏗️ Construction & Building
        {'name': 'Masonry', 'description': 'Bricklaying, Concrete Work', 'icon': 'brick'},
        {'name': 'Carpentry', 'description': 'Carpentry & Woodwork', 'icon': 'hammer'},
        {'name': 'Roofing', 'description': 'Roofing & Waterproofing', 'icon': 'house'},
        {'name': 'Tiling', 'description': 'Tiling & Flooring', 'icon': 'tile'},
        {'name': 'Painting', 'description': 'Painting & Decoration', 'icon': 'paint-roller'},
        {'name': 'Drywall', 'description': 'Drywall Installation', 'icon': 'layer-group'},
        {'name': 'Steel Fabrication', 'description': 'Steel Fabrication', 'icon': 'industry'},
        {'name': 'Glass Work', 'description': 'Glass & Aluminum Work', 'icon': 'glass-whiskey'},
        
        # ⚡ Electrical Services
        {'name': 'Electrical Wiring', 'description': 'Electrical Wiring & Installation', 'icon': 'bolt'},
        {'name': 'Lighting', 'description': 'Lighting Installation', 'icon': 'lightbulb'},
        {'name': 'Generator Repair', 'description': 'Generator Installation & Repair', 'icon': 'charging-station'},
        {'name': 'Solar Installation', 'description': 'Solar System Installation', 'icon': 'solar-panel'},
        {'name': 'Inverter Systems', 'description': 'Inverter & UPS Systems', 'icon': 'plug'},
        {'name': 'Security Systems', 'description': 'Security & CCTV Installation', 'icon': 'shield-alt'},
        {'name': 'Home Automation', 'description': 'Home Automation & Smart Systems', 'icon': 'home'},
        
        # 🚰 Plumbing Services
        {'name': 'Plumbing', 'description': 'General Plumbing', 'icon': 'faucet'},
        {'name': 'Pipe Fitting', 'description': 'Pipe Fitting & Installation', 'icon': 'pipe'},
        {'name': 'Water Heater', 'description': 'Water Heater Installation', 'icon': 'temperature-high'},
        {'name': 'Borehole', 'description': 'Borehole Drilling & Maintenance', 'icon': 'water'},
        {'name': 'Water Treatment', 'description': 'Water Treatment Systems', 'icon': 'filter'},
        {'name': 'Septic Tank', 'description': 'Septic Tank Installation', 'icon': 'toilet'},
        {'name': 'Drainage', 'description': 'Drainage & Sewer Systems', 'icon': 'water'},
        
        # ❄️ HVAC & Cooling
        {'name': 'AC Installation', 'description': 'Air Conditioner Installation', 'icon': 'snowflake'},
        {'name': 'AC Repair', 'description': 'Air Conditioner Repair', 'icon': 'tools'},
        {'name': 'AC Maintenance', 'description': 'AC Maintenance & Servicing', 'icon': 'wrench'},
        {'name': 'Refrigeration', 'description': 'Refrigeration Systems', 'icon': 'temperature-low'},
        {'name': 'Ventilation', 'description': 'Ventilation Systems', 'icon': 'fan'},
        {'name': 'Cold Room', 'description': 'Cold Room Installation', 'icon': 'warehouse'},
        
        # 🏠 Home Services
        {'name': 'Cleaning', 'description': 'Cleaning & Janitorial', 'icon': 'broom'},
        {'name': 'Pest Control', 'description': 'Pest Control & Fumigation', 'icon': 'bug'},
        {'name': 'Laundry', 'description': 'Laundry & Dry Cleaning', 'icon': 'tshirt'},
        {'name': 'Gardening', 'description': 'Gardening & Landscaping', 'icon': 'leaf'},
        {'name': 'Home Organizing', 'description': 'Home Organizing', 'icon': 'boxes'},
        {'name': 'Moving', 'description': 'Moving & Relocation', 'icon': 'truck-moving'},
        
        # 🔧 Mechanical & Automotive
        {'name': 'Auto Repair', 'description': 'Automobile Repair', 'icon': 'car'},
        {'name': 'Auto Electrician', 'description': 'Auto Electrician', 'icon': 'car-battery'},
        {'name': 'Panel Beating', 'description': 'Panel Beating & Spraying', 'icon': 'hammer'},
        {'name': 'Generator Maintenance', 'description': 'Generator Maintenance', 'icon': 'cog'},
        {'name': 'Elevator Repair', 'description': 'Elevator & Escalator Repair', 'icon': 'arrow-up'},
        {'name': 'Industrial Machines', 'description': 'Industrial Machine Repair', 'icon': 'cogs'},
        
        # 💻 Technology & IT
        {'name': 'Computer Repair', 'description': 'Computer & Laptop Repair', 'icon': 'laptop'},
        {'name': 'Phone Repair', 'description': 'Phone & Tablet Repair', 'icon': 'mobile-alt'},
        {'name': 'Network Setup', 'description': 'Network & WiFi Setup', 'icon': 'wifi'},
        {'name': 'Smartphone Repair', 'description': 'Smartphone Repair', 'icon': 'mobile'},
        {'name': 'TV Repair', 'description': 'TV & Electronics Repair', 'icon': 'tv'},
        {'name': 'Sound Systems', 'description': 'Sound System Installation', 'icon': 'volume-up'},
        
        # 🛋️ Furniture & Interior
        {'name': 'Furniture Making', 'description': 'Furniture Making', 'icon': 'chair'},
        {'name': 'Upholstery', 'description': 'Upholstery & Repair', 'icon': 'couch'},
        {'name': 'Curtains', 'description': 'Curtains & Blinds Installation', 'icon': 'window-restore'},
        {'name': 'Interior Design', 'description': 'Interior Design', 'icon': 'palette'},
        {'name': 'Cabinet Making', 'description': 'Cabinet Making', 'icon': 'archive'},
        
        # 🔩 Metal Work
        {'name': 'Welding', 'description': 'Welding & Fabrication', 'icon': 'fire'},
        {'name': 'Blacksmith', 'description': 'Blacksmithing', 'icon': 'hammer'},
        {'name': 'Gate Making', 'description': 'Gate & Fence Making', 'icon': 'gate'},
        {'name': 'Metal Doors', 'description': 'Metal Doors & Windows', 'icon': 'door-closed'},
        {'name': 'Iron Bending', 'description': 'Iron Bending', 'icon': 'tools'},
        
        # 💅 Beauty & Personal Care
        {'name': 'Hair Styling', 'description': 'Hair Styling & Barbering', 'icon': 'cut'},
        {'name': 'Makeup Artist', 'description': 'Makeup Artist', 'icon': 'spray-can'},
        {'name': 'Nail Technician', 'description': 'Nail Technician', 'icon': 'hand-paper'},
        {'name': 'Spa Services', 'description': 'Spa & Massage Therapy', 'icon': 'spa'},
        {'name': 'Tailoring', 'description': 'Tailoring & Fashion Design', 'icon': 'tshirt'},
        
        # 🎉 Event Services
        {'name': 'Catering', 'description': 'Catering & Cooking', 'icon': 'utensils'},
        {'name': 'Photography', 'description': 'Photography & Videography', 'icon': 'camera'},
        {'name': 'Event Decoration', 'description': 'Event Decoration', 'icon': 'glass-cheers'},
        {'name': 'DJ Services', 'description': 'DJ & Sound Services', 'icon': 'music'},
        {'name': 'MC Services', 'description': 'MC & Event Hosting', 'icon': 'microphone'},
        
        # 👔 Professional Services
        {'name': 'Tutoring', 'description': 'Tutoring & Teaching', 'icon': 'chalkboard-teacher'},
        {'name': 'Graphic Design', 'description': 'Graphic Design', 'icon': 'paint-brush'},
        {'name': 'Writing', 'description': 'Writing & Editing', 'icon': 'pen'},
        {'name': 'Web Development', 'description': 'Web Development', 'icon': 'code'},
        {'name': 'Legal Services', 'description': 'Legal Services', 'icon': 'balance-scale'},
        {'name': 'Accounting', 'description': 'Accounting & Bookkeeping', 'icon': 'calculator'},
        
        # 🏥 Health & Wellness
        {'name': 'Fitness Training', 'description': 'Fitness Training', 'icon': 'running'},
        {'name': 'Yoga Instruction', 'description': 'Yoga Instruction', 'icon': 'spa'},
        {'name': 'Nutritionist', 'description': 'Nutritionist', 'icon': 'apple-alt'},
        {'name': 'Home Nursing', 'description': 'Home Nursing Care', 'icon': 'heartbeat'},
        {'name': 'Therapy', 'description': 'Physical Therapy', 'icon': 'hands-helping'},
        
        # 🚚 Logistics & Delivery
        {'name': 'Delivery Services', 'description': 'Delivery Services', 'icon': 'shipping-fast'},
        {'name': 'Transportation', 'description': 'Transportation Services', 'icon': 'bus'},
        {'name': 'Errand Running', 'description': 'Errand Running', 'icon': 'walking'},
        {'name': 'Courier Services', 'description': 'Courier Services', 'icon': 'envelope'},
        
        # 📋 Other Services
        {'name': 'Laundry', 'description': 'Laundry & Ironing', 'icon': 'tshirt'},
        {'name': 'Child Care', 'description': 'Child Care Services', 'icon': 'baby'},
        {'name': 'Elderly Care', 'description': 'Elderly Care Services', 'icon': 'user-friends'},
        {'name': 'Pet Care', 'description': 'Pet Care & Grooming', 'icon': 'paw'},
        {'name': 'Other', 'description': 'Other Services', 'icon': 'ellipsis-h'},
    ]
    
    for cat_data in categories:
        # Check if category already exists
        existing = ServiceCategory.query.filter_by(name=cat_data['name']).first()
        if not existing:
            category = ServiceCategory(
                name=cat_data['name'],
                description=cat_data.get('description', ''),
                icon=cat_data.get('icon', 'tools')
            )
            db.session.add(category)
    
    db.session.commit()
    print(f"Added {len(categories)} service categories to database")



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