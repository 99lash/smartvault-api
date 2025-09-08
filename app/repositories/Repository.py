from sqlalchemy.orm import Session
from datetime import datetime

class Repository:
    def __init__(self, db: Session, model):
        self.db = db
        self.model = model

    def get_all(self):
        return self.db.query(self.model).all()

    def get_by_id(self, record_id: int):
        return self.db.query(self.model).filter(self.model.id == record_id).first()

    def create(self, **kwargs):
        obj = self.model(**kwargs)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, record_id: int, **kwargs):
        obj = self.get_by_id(record_id)
        if not obj:
            return None
        for key, value in kwargs.items():
            setattr(obj, key, value)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, record_id: int):
        obj = self.get_by_id(record_id)
        if not obj:
            return None
        if hasattr(obj, "deleted_at"):
            obj.deleted_at = datetime.utcnow()  # soft delete
        else:
            self.db.delete(obj)  # hard delete
        self.db.commit()
        return obj
