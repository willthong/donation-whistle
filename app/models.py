from datetime import datetime

from app import db


class DonorType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donors = db.relationship("DonorAlias", backref="type", lazy="dynamic")
    donations = db.relationship("Donation", backref="type", lazy="dynamic")
    name = db.Column(db.String(25))


class DonorAlias(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Integer, db.ForeignKey("donor_type.id"))
    name = db.Column(db.String(100), index=True)
    last_edited = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    donors = db.relationship("Donor", backref="alias", lazy="dynamic")
    donations = db.relationship("Donation", backref="donor", lazy="dynamic")
    ec_donor_id = db.Column(db.Integer)
    # Would need to add an accounting unit ID to add non-central donations
    ec_regulated_entity_id = db.Column(db.Integer)
    postcode = db.Column(db.String(7))

    def __repr__(self):
        return f"<Donor {self.name}>"


class Donor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alias = db.Column(db.Integer, db.ForeignKey("donor_alias.id"))
    name = db.Column(db.String(100), index=True)

    def __repr__(self):
        return f"<Donor (Backend) {self.name}>"


class Recipient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), index=True)
    deregistered = db.Column(db.Date)

    def __repr__(self):
        return f"<Recipient {self.name}>"


class DonationTypes(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), index=True)

    def __repr__(self):
        return f"<Donation Type {self.name}>"


class Donation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor = db.Column(db.Integer, db.ForeignKey("donor_alias.id"))
    recipient = db.Column(db.Integer, db.ForeignKey("recipient.id"))
    type = db.Column(db.Integer, db.ForeignKey("donor_type.id"))
    value = db.Column(db.Float, index=True)
    date = db.Column(db.Date, index=True)
    ec_ref = db.Column(db.String(8))
    is_legacy = db.Column(db.Boolean, index=True)

    def __repr__(self):
        return f"<Donation of £{self.value} from {self.donor.name} to {self.recipient.name} on {self.date}>"
