import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URI', 'mysql+pymysql://root:@localhost/club_management')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Configuración de Flask-Mail
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.tu-servidor.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', 'tu_correo@dominio.com')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', 'tu_contraseña')
    MAIL_DEFAULT_SENDER = MAIL_USERNAME

    
