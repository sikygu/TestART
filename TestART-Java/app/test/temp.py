from app.database import Database
from app.classes import BatchAttemptStatus

db = Database()
status = db.get(4)
print(status)