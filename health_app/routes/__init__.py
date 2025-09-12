from flask import Flask

def create_app():
    """
    Factory function to create and configure the Flask app.
    Blueprints are registered here to avoid circular imports.
    """
    app = Flask(__name__)

    # Example: register blueprints
    from health_app.routes.symptoms import symptoms_bp
    from health_app.routes.medications import medications_bp
    from health_app.routes.profile import profile_bp

    app.register_blueprint(symptoms_bp, url_prefix="/symptoms")
    app.register_blueprint(medications_bp, url_prefix="/medications")
    app.register_blueprint(profile_bp, url_prefix="/profile")

    return app
