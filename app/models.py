from datetime import datetime
from typing import List, Optional

from app import db


class DonorType(db.Model):
    __tablename__ = "donor_type"

    id: db.Mapped[int] = db.mapped_column(db.Integer, primary_key=True)
    # Not bidirectional - I don't need to see all the donors from the type record
    donors: db.Mapped[List["Donor"]] = db.relationship()
    name = db.mapped_column(db.String(25))


class DonorAlias(db.Model):
    __tablename__ = "donor_alias"

    id = db.mapped_column(db.Integer, primary_key=True)
    name = db.mapped_column(db.String(100), index=True)
    last_edited = db.mapped_column(db.DateTime, default=datetime.utcnow, index=True)
    donors: db.Mapped[List["Donor"]] = db.relationship(back_populates="donor_aliases")

    def __repr__(self):
        return f"<Donor {self.name}>"


class Donor(db.Model):
    __tablename__ = "donor"

    id = db.mapped_column(db.Integer, primary_key=True)
    donor_alias_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("donor_alias.id"))
    donor_aliases: db.Mapped[List["DonorAlias"]] = db.relationship(back_populates="donors")
    donor_type_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("donor_type.id"))
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
    # Not bydirectional: I don't need to see all applicable donations from the donation type
    # record
    donations: db.Mapped[List["Donation"]] = db.relationship()

    def __repr__(self):
        return f"<Donation Type {self.name}>"


class Donation(db.Model):
    __tablename__ = "donation"

    id = db.mapped_column(db.Integer, primary_key=True)
    donor_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("donor.id"))
    donor: db.Mapped["Donor"] = db.relationship(back_populates="donations")
    recipient_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("recipient.id"))
    recipient: db.Mapped["Recipient"] = db.relationship(back_populates="donations")
    donation_type_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("donation_type.id"))
    value = db.mapped_column(db.Float, index=True)
    date = db.mapped_column(db.Date, index=True)
    ec_ref = db.mapped_column(db.String(8))
    is_legacy = db.mapped_column(db.Boolean, index=True)

    def __repr__(self):
        return f"<Donation of £{self.value} from {self.donor.name} to {self.recipient.name} on {self.date}>"

