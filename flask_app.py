from app.models import db
from app import create_app

app = create_app("ProductionConfig")



with app.app_context():
    # db.drop_all()
    db.create_all() 

# app.run()

