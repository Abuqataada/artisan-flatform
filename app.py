from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_cors import CORS
from config import Config
from models import db, User, Artisan, Admin
import os
from dotenv import load_dotenv

login_manager = LoginManager()
migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Configure login manager
    login_manager.login_view = 'user_routes.login'
    login_manager.login_message_category = 'info'
    
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
    from .routes.user_routes import user_bp
    from .routes.admin_routes import admin_bp
    from .routes.artisan_routes import artisan_bp
    
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(port=port, debug=debug)