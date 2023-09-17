from datetime import datetime

from flask import request

from app import app, db, cache
from app.models import (
    Donor,
    DonorAlias,
    Donation,
    Recipient,
    DonationType,
)
from app.routes import populate_filter_statements, OTHER_DONATION_TYPES, OTHER_DONOR_TYPES
from app.api import bp

CRIT_LOOKUPS = {
    "donor": Donor.name,
    "recipient": Recipient.name,
    "date": Donation.date,
    "value": Donation.value,
}


def apply_sort(query):
    sort = request.args.get("sort")
    if not sort:
        return query.order_by(Donation.date.desc())
    for s in sort.split(","):
        criterion = s[1:]
        criterion = CRIT_LOOKUPS[criterion] if criterion in CRIT_LOOKUPS else Donation.date
        print(criterion)
        direction = s[0]
        return query.order_by(criterion.desc()) if direction == "-" else query.order_by(criterion)


@app.route("/api/data")
@cache.cached(timeout=600000, query_string=True)
# https://stackoverflow.com/a/47181782
def data():
    query = db.select(Donation).join(Recipient).join(Donor).join(DonationType).join(DonorAlias)

    # Filtering
    # Multiple identically named keys => weird dictionary-like object to which we must
    # apply .getlist() rather than looping through as we would a normal dict
    # https://tedboy.github.io/flask/generated/generated/werkzeug.MultiDict.html)
    all_filters = request.args.getlist("filter")

    # Populate filter types
    recipient_filters, donor_type_filters, donation_type_filters, is_legacy_filters = [], [], [], []
    donor_alias_filters, start_date_filter, end_date_filter = [], None, None

    for filter in all_filters:
        if filter.startswith("recipient"): recipient_filters.append(filter)
        if filter.startswith("donor_type"): donor_type_filters.append(filter)
        if filter.startswith("donation_type"): donation_type_filters.append(filter)
        if filter == "donation_type_other": donation_type_filters.extend(OTHER_DONATION_TYPES)
        if filter.startswith("is_legacy"): is_legacy_filters.append(filter)
        if filter.startswith("donor_alias"): donor_alias_filters.append(filter)
        if filter.startswith("date_gt_"):
            start_date_filter = datetime.strptime(filter[-10:], "%Y-%m-%d")
        if filter.startswith("date_lt_"):
            end_date_filter = datetime.strptime(filter[-10:], "%Y-%m-%d")

    # Each filter bucket is an additional group of ORs added as an AND, so need to be 
    # grouped together
    recipient_filter_statements = populate_filter_statements(
        recipient_filters, "recipient_", Recipient.name
    )
    donor_type_filter_statements = populate_filter_statements(
        donor_type_filters, "donor_type_", Donor.donor_type_id
    )
    donation_type_filter_statements = populate_filter_statements(
        donation_type_filters, "donation_type_", DonationType.name
    )
    donor_alias_filter_statements = populate_filter_statements(
        donor_alias_filters, "donor_alias_", DonorAlias.id
    )

    if recipient_filter_statements and ("recipient_other" in all_filters):
        query = query.where(db.or_(
            *recipient_filter_statements,
            db.and_(
                Recipient.name != "Labour Party",
                Recipient.name != "Conservative and Unionist Party",
                Recipient.name != "Liberal Democrats",
                Recipient.name != "Scottish National Party (SNP)",
                Recipient.name != "Green Party",
                Recipient.name != "Reform UK",
            ),
        ))
    if recipient_filter_statements and ("recipient_other" not in all_filters):
        query = query.where(db.or_(*recipient_filter_statements))
    if donor_type_filter_statements:
        query = query.where(db.or_(*donor_type_filter_statements))
    if donation_type_filter_statements:
        query = query.where(db.or_(*donation_type_filter_statements))
    if donor_alias_filter_statements:
        query = query.where(db.or_(*donor_alias_filter_statements))
    if "is_legacy_false" in is_legacy_filters and "is_legacy_true" not in is_legacy_filters:
        query = query.where(Donation.is_legacy == False)
    if "is_legacy_true" in is_legacy_filters and "is_legacy_false" not in is_legacy_filters:
        query = query.where(Donation.is_legacy == True)
    if start_date_filter:
        query = query.where(Donation.date >= start_date_filter)
    if end_date_filter:
        query = query.where(Donation.date <= end_date_filter)

    # Search filter
    search = request.args.get("search")
    if search:
        # Filter so that Donation.donor.name matches. You must use a where clause
        # https://docs.sqlalchemy.org/en/20/tutorial/data_select.html#the-where-clause
        # TODO: check if this is a bug because it should be looking at Aliases. Or maybe
        # it should be doing both!
        query = query.where(Donor.name.ilike(f"%{search}%"),)
    total = len(list(db.session.scalars(query)))

    # Sorting
    query = apply_sort(query)

    # Pagination
    start = request.args.get("start", type=int, default=-1)
    length = request.args.get("length", type=int, default=-1)
    if start != -1 and length != -1:
        query = query.offset(start).limit(length)

    # Response
    return {
        "data": [donation.to_dict() for donation in db.session.scalars(query)],
        "total": total,
    }

