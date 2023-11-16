from app import create_app, db, cache
from app.models import (
    User,
    DonorType, 
    DonorAlias, 
    Donor, 
    Recipient, 
    DonationType,
    Donation, 
    Task, 
    Notification
)

app = create_app()
# Obviate shell imports

@app.shell_context_processor
def make_shell_context():
    return {
        "db": db,
        "cache": cache,
        'User': User,
        'DonorType': DonorType, 
        'DonorAlias': DonorAlias, 
        'Donor': Donor, 
        'Recipient': Recipient, 
        'DonationType': DonationType,
        'Donation': Donation, 
        'Task': Task, 
        'Notification': Notification,
    }
