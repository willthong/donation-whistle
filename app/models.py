from datetime import datetime
import redis
import rq
from typing import List
from werkzeug.security import generate_password_hash, check_password_hash

from flask import current_app
from flask_login import UserMixin

from app import db, login


class DonorType(db.Model):
    __tablename__ = "donor_type"

    id: db.Mapped[int] = db.mapped_column(db.Integer, primary_key=True)
    # Not bidirectional - I don't need to see all the donors from the type record
    donors: db.Mapped[List["Donor"]] = db.relationship()
    name = db.mapped_column(db.String(25))
    display_name = db.mapped_column(db.String(25))


class DonorAlias(db.Model):
    __tablename__ = "donor_alias"

    id = db.mapped_column(db.Integer, primary_key=True)
    name = db.mapped_column(db.String(100), index=True)
    last_edited = db.mapped_column(db.DateTime, default=datetime.utcnow, index=True)
    note = db.mapped_column(db.String(1000))
    donors: db.Mapped[List["Donor"]] = db.relationship(back_populates="donor_alias")

    def __repr__(self):
        return f"<Donor {self.name}>"


class Donor(db.Model):
    __tablename__ = "donor"

    id = db.mapped_column(db.Integer, primary_key=True)
    donor_alias_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("donor_alias.id"))
    donor_alias: db.Mapped[List["DonorAlias"]] = db.relationship(
        back_populates="donors"
    )
    donor_type_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("donor_type.id"))
    donor_type: db.Mapped["DonorType"] = db.relationship(back_populates="donors")
    donations: db.Mapped[List["Donation"]] = db.relationship(back_populates="donor")
    name = db.mapped_column(db.String(100), index=True)
    ec_donor_id = db.mapped_column(db.Integer)
    # Would need to add an accounting unit ID to add non-central donations
    ec_regulated_entity_id = db.mapped_column(db.Integer)
    postcode = db.mapped_column(db.String(7))
    company_registration_number = db.mapped_column(db.Integer)

    def __repr__(self):
        return f"<Donor (Backend) {self.name}>"


class Recipient(db.Model):
    __tablename__ = "recipient"

    id = db.mapped_column(db.Integer, primary_key=True)
    name = db.mapped_column(db.String(100), index=True)
    deregistered = db.mapped_column(db.Date)
    donations: db.Mapped[List["Donation"]] = db.relationship(back_populates="recipient")

    def __repr__(self):
        return f"<Recipient {self.name}>"


class DonationType(db.Model):
    __tablename__ = "donation_type"

    id = db.mapped_column(db.Integer, primary_key=True)
    name = db.mapped_column(db.String(100), index=True)
    donations: db.Mapped[List["Donation"]] = db.relationship(
        back_populates="donation_type"
    )

    def __repr__(self):
        return f"{self.name}"


class Donation(db.Model):
    __tablename__ = "donation"

    id = db.mapped_column(db.Integer, primary_key=True)
    donor_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("donor.id"))
    donor: db.Mapped["Donor"] = db.relationship(back_populates="donations")
    recipient_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("recipient.id"))
    recipient: db.Mapped["Recipient"] = db.relationship(back_populates="donations")
    donation_type_id: db.Mapped[int] = db.mapped_column(
        db.ForeignKey("donation_type.id")
    )
    donation_type: db.Mapped["DonationType"] = db.relationship(
        back_populates="donations"
    )
    value = db.mapped_column(db.Float, index=True)
    date = db.mapped_column(db.Date, index=True)
    ec_ref = db.mapped_column(db.String(8))
    is_legacy = db.mapped_column(db.Boolean, index=True)

    def __repr__(self):
        return f"<Donation of £{self.value} from {self.donor.name} to {self.recipient.name} on {self.date}>"

    def to_dict(self):
        """Prepares a dictionary for the API"""
        return {
            "donor": self.donor.donor_alias.name,
            "donor_type": self.donor.donor_type_id,
            "alias_id": self.donor.donor_alias.id,
            "recipient": self.recipient.name,
            "recipient_id": self.recipient.id,
            "date": self.date,
            "type": self.donation_type.name,
            "amount": self.value,
            "legacy": self.is_legacy,
            "original_donor_name": self.donor.name,
            "electoral_commission_donor_id": self.donor.ec_donor_id,
            "electoral_commission_donation_id": self.ec_ref,
        }


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.mapped_column(db.Integer, primary_key=True)
    username = db.mapped_column(db.String(64), index=True, unique=True)
    email = db.mapped_column(db.String(120), index=True, unique=True)
    password_hash = db.mapped_column(db.String(128))
    # Admins can add other users and import data. Normal users can only add aliases.
    is_admin = db.mapped_column(db.Boolean, index=True)
    tasks: db.Mapped[List["Task"]] = db.relationship(back_populates="user")

    # Preparing for eventual API
    token = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)

    def __repr__(self):
        return f"<User {self.username}>"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def launch_task(self, *args, **kwargs):
        rq_job = current_app.task_queue.enqueue(
            "app.db_import.tasks.db_import", self.id, *args, **kwargs
        )
        task = Task(id=rq_job.get_id(), user=self)
        db.session.add(task)
        db.session.commit()
        return task

    def get_task_in_progress(self):
        return db.session.scalars(db.select(Task).filter_by(user = self)).first()


@login.user_loader
def load_user(id):
    return db.session.query(User).filter_by(id=id).first()


class Task(db.Model):  # Store request context after request has vanished
    __tablename__ = "task"
    id = db.mapped_column(db.String(36), primary_key=True)  # generated by RQ
    user_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("user.id"))
    user: db.Mapped["User"] = db.relationship(back_populates="tasks")
    complete = db.mapped_column(db.Boolean)

    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None
        return rq_job

    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get("progress", 0) if job is not None else 100


# TODO: donation makeup bar chart, comparative. Only needs to be annual.
