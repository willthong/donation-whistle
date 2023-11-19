import csv
import datetime as dt
import dateutil.relativedelta as relativedelta
import plotly.graph_objects as go
import requests
import werkzeug

from flask import flash, jsonify, redirect, request, render_template, send_file, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (
    DataRequired,
)

from app import db
from app.models import (
    User,
    DonorAlias,
    Donor,
    Donation,
    Notification,
    Recipient,
    DonationType,
)
from app.main.forms import (
    LoginForm,
    RegistrationForm,
    DeleteUserForm,
    FilterForm,
)
from app.main import bp

OTHER_DONOR_TYPES = [
    "donor_type_building_society",
    "donor_type_public_fund",
    "donor_type_impermissible_donor",
    "donor_type_na",
    "donor_type_unidentifiable_donor",
]
OTHER_DONATION_TYPES = [
    "donation_type_public_funds",
    "donation_type_exempt_trust",
    "donation_type_permissible_donor_exempt_trust",
    "donation_type_impermissible_donor",
    "donation_type_unidentified_donor",
]
DEFAULT_FILTERS = "filter=recipient_labour_party&filter=recipient_conservative_and_unionist_party&filter=recipient_liberal_democrats&filter=recipient_scottish_national_party_snp&filter=recipient_green_party&filter=recipient_reform_uk&filter=recipient_other&filter=is_legacy_true&filter=is_legacy_false&filter=donor_type_individual&filter=donor_type_company&filter=donor_type_limited_liability_partnership&filter=donor_type_trade_union&filter=donor_type_unincorporated_association&filter=donor_type_trust&filter=donor_type_friendly_society&filter=donation_type_cash&filter=donation_type_non_cash&filter=donation_type_visit"

DEFAULT_FILTERS_NO_RECIPIENTS = "&filter=is_legacy_true&filter=is_legacy_false&filter=donor_type_individual&filter=donor_type_company&filter=donor_type_limited_liability_partnership&filter=donor_type_trade_union&filter=donor_type_unincorporated_association&filter=donor_type_trust&filter=donor_type_friendly_society&filter=donation_type_cash&filter=donation_type_non_cash&filter=donation_type_visit"

DONOR_TYPE_COLOURS = {
    "Individual": "indigo",
    "Company": "slateblue",
    "Limited Liability Partnership": "seagreen",
    "Trade Union": "hotpink",
    "Unincorporated Association": "yellow",
    "Other": "black",
}

PARTY_COLOURS = {
    "Conservative and Unionist Party": "rgb(0, 135, 220)",
    "Labour Party": "rgb(228, 0, 59)",
    "Liberal Democrats": "rgb(255, 159, 26)",
    "Reform UK": "rgb(0, 146, 180)",
}

MAIN_PARTIES = [
    "Conservative and Unionist Party",
    "Labour Party",
    "Liberal Democrats",
    "Reform UK",
    "All other parties",
]

PRETTY_FIELD_NAMES = {
    "electoral_commission_donation_id": "Electoral Commission donation ID",
    "electoral_commission_donor_id": "Electoral Commission donor ID",
    "date": "Donation date",
    "donor": "Donor name (alias)",
    "original_donor_name": "Original donor name",
    "alias_id": "Donor alias ID",
    "donor_type": "Donor type",
    "recipient": "Recipient name",
    "recipient_id": "Recipient ID",
    "type": "Donation type",
    "amount": "Donation amount",
    "legacy": "Is legacy?",
}

class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Sign In")


@bp.route("/", methods=["GET", "POST"])
@bp.route("/index", methods=["GET", "POST"])
def index():
    form = FilterForm()

    if form.validate_on_submit():
        filter_list = [par for par in request.form.keys() if request.form[par] == "y"]
        if request.form["date_gt"]:  # pragma: no cover
            filter_list.append("date_gt_" + request.form["date_gt"])
        if request.form["date_lt"]:  # pragma: no cover
            filter_list.append("date_lt_" + request.form["date_lt"])
        return redirect(
            url_for(
                "main.index",
                filter=filter_list,
            )
        )
    # The api_filter parameter will be appended to the API URL by the template
    filter_string = request.query_string.decode() or DEFAULT_FILTERS
    return render_template(
        "index.html", title="Home", form=form, api_filter=filter_string
    )


def populate_filter_statements(filters, prefix, db_field):
    output = []
    for filter in filters:
        filter = (
            filter.replace(prefix, "")
            .replace("_", " ")
            .replace("(", "")
            .replace(")", "")
        )
        filter = (
            db.func.REPLACE(db.func.REPLACE(db.func.lower(db_field), "(", ""), ")", "")
            == filter
        )
        output.append(filter)
    return output


def apply_date_filters(query, all_filters):
    for filter in all_filters:
        if filter.startswith("date_gt_"):
            query = query.where(
                Donation.date >= dt.datetime.strptime(filter[-10:], "%Y-%m-%d")
            )
        if filter.startswith("date_lt_"):
            query = query.where(
                Donation.date <= dt.datetime.strptime(filter[-10:], "%Y-%m-%d")
            )
    return query


def assign_colours_to_donor_types(query, index):
    """Takes a query and the donor type's relevant index. Assigns each record in that
    query according to the DONOR_TYPE_COLOURS variable. Returns a list of the donor type
    colours and a dictionary with duplicates removed for the key."""
    donor_type, relevant_types = [], {}
    for record in query:
        if record[index] in DONOR_TYPE_COLOURS:  # pragma: no cover
            donor_type.append(DONOR_TYPE_COLOURS[record[index]])
            if DONOR_TYPE_COLOURS[record[index]] not in relevant_types:
                relevant_types[record[index]] = DONOR_TYPE_COLOURS[record[index]]
        if record[index] not in DONOR_TYPE_COLOURS:
            donor_type.append("black")
            relevant_types["Other"] = "black"
    return donor_type, relevant_types


@bp.route(
    "/recipient",
    methods=[
        "GET",
    ],
)
def recipient_dummy():  # pragma: no cover
    # Dummy route to allow for URL construction
    pass


@bp.route("/recipient/<int:id>", methods=["GET", "POST"])
def recipient(id):
    recipient = db.get_or_404(Recipient, id)
    title = recipient.name

    form = FilterForm()

    if form.validate_on_submit():  # pragma: no cover
        filter_list = []
        if request.form["date_gt"]:
            filter_list.append("date_gt_" + request.form["date_gt"])
        if request.form["date_lt"]:
            filter_list.append("date_lt_" + request.form["date_lt"])
        return redirect(
            url_for(
                "main.recipient",
                id=id,
                filter=filter_list,
            )
        )

    all_filters = request.args.getlist("filter")
    donation_type_filter_statements = populate_filter_statements(
        OTHER_DONATION_TYPES, "donation_type_", DonationType.name
    )
    donor_type_filter_statements = populate_filter_statements(
        OTHER_DONOR_TYPES, "donor_type_", Donor.donor_type_id
    )

    top_donor_query = (
        db.session.query(
            DonorAlias.name,
            Donor.donor_type_id,
            db.func.sum(Donation.value).label("donations"),
            db.func.min(Donation.date).label("first_gift"),
            db.func.max(Donation.date).label("latest_gift"),
        )
        .join(Donor.donor_alias)
        .join(Donation)
        .join(Recipient)
        .join(DonationType)
        .where(Recipient.name == recipient.name)
        .where(db.not_(db.or_(*donation_type_filter_statements)))
        .where(db.not_(db.or_(*donor_type_filter_statements)))
        .group_by(DonorAlias.name)
        .order_by(db.desc("donations"))
    )
    top_donor_query = apply_date_filters(top_donor_query, all_filters)
    top_donor_query = top_donor_query.limit(100).all()

    top_donors = [record[0] for record in top_donor_query]
    donor_type, relevant_types = assign_colours_to_donor_types(top_donor_query, 1)
    donations = [record[2] for record in top_donor_query]
    first_gift = [record[3] for record in top_donor_query]
    latest_gift = [record[4] for record in top_donor_query]

    top_donor_graph = go.Figure(
        data=[
            go.Bar(
                x=top_donors,
                y=donations,
                customdata=list(zip(first_gift, latest_gift)),
                hovertemplate="£%{y:.4s}"
                "<extra>First Gift: %{customdata[0]}<br>Latest Gift: %{customdata[1]}</extra>",
                marker_color=donor_type,
                showlegend=False,
            ),
        ],
        layout={
            "title": "Top Donors",
            "xaxis": {"title": "", "range": [-0.5, 10.5]},
            "yaxis": {"title": "£", "type": "linear"},
            "legend": {
                "x": 0,
                "y": 1.02,
                "bgcolor": "rgba(255,255,255,0)",
                "bordercolor": "rgba(255,255,255,0)",
                "orientation": "h",
                "yanchor": "bottom",
            },
            "hovermode": "closest",
            "font_family": "'Helvetica Neue', 'Open Sans', Arial",
        },
    )

    for donor_type, colour in relevant_types.items():
        top_donor_graph.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                name=donor_type,
                marker_color=colour,
                line={"color": "rgba(0,0,0,0.0)"},
                marker={"size": 80},
            ),
        )

    donation_sources_query = (
        db.session.query(
            Donor.donor_type_id, db.func.sum(Donation.value).label("donations")
        )
        .join(Donation)
        .join(DonationType)
        .join(Recipient)
        .filter(Recipient.name == recipient.name)
        .filter(db.not_(db.or_(*donation_type_filter_statements)))
        .filter(db.not_(db.or_(*donor_type_filter_statements)))
        .group_by(Donor.donor_type_id)
        .order_by(db.desc("donations"))
    )
    donation_sources_query = apply_date_filters(donation_sources_query, all_filters)
    donation_sources_query = donation_sources_query.all()

    sources = [record[0] for record in donation_sources_query]
    donations_by_source = [record[1] for record in donation_sources_query]
    donor_type, relevant_types = assign_colours_to_donor_types(
        donation_sources_query, 0
    )

    donation_sources_graph = go.Figure(
        data=[
            go.Bar(
                x=donations_by_source,
                y=sources,
                showlegend=False,
                hovertemplate="£%{x:.4s}<extra></extra>",
                orientation="h",
                marker_color=donor_type,
            ),
        ],
        layout={
            "title": "Source of funds",
            "yaxis": {
                "title": "",
            },
            "xaxis": {
                "title": "£",
                "type": "linear",
            },
            "font_family": "'Helvetica Neue', 'Open Sans', Arial",
        },
    )
    donation_sources_graph.update_yaxes(
        range=(-0.5, 2.5), constrain="domain", ticksuffix=" "
    )

    # Prepare filter_list for link to full donations list
    filter_list = "?filter=recipient_"
    filter_list += recipient.name.lower().replace(" ", "_")
    filter_list += DEFAULT_FILTERS_NO_RECIPIENTS

    return render_template(
        "recipient.html",
        title=title,
        recipient=recipient,
        top_donor_graph=top_donor_graph.to_json(),
        donation_sources_graph=donation_sources_graph.to_json(),
        form=form,
        filter_list=filter_list,
    )


def assign_colours_to_parties(party):
    if party in PARTY_COLOURS:
        return PARTY_COLOURS[party]
    return "black"


@bp.route("/donor/<int:id>", methods=["GET", "POST"])
def donor(id):
    """This is ultimately a user-facing view of aliases"""
    alias = db.get_or_404(DonorAlias, id)
    title = alias.name

    form = FilterForm()

    if form.validate_on_submit():  # pragma: no cover
        filter_list = []
        if request.form["date_gt"]:
            filter_list.append("date_gt_" + request.form["date_gt"])
        if request.form["date_lt"]:
            filter_list.append("date_lt_" + request.form["date_lt"])
        return redirect(
            url_for(
                "main.donor",
                id=id,
            )
        )

    # Total giving over time bar graph
    gifts_query = (
        db.session.query(
            Recipient.name,
            db.func.strftime("%Y", Donation.date).label("year"),
            db.func.sum(Donation.value),
        )
        .join(Donor.donations)
        .join(Recipient)
        .join(DonorAlias)
        .where(DonorAlias.name == alias.name)
        .order_by(Donation.date)
        .group_by("year", Recipient.name)
    ).all()

    bar_names = list(set([record[0] for record in gifts_query]))
    dates = [record[1] for record in gifts_query]
    start_year, end_year, date_series = int(dates[0]), int(dates[-1]), []
    while start_year <= end_year:
        date_series.append(start_year)
        start_year += 1

    parties = {}
    for key in bar_names:
        parties[key] = [0] * len(date_series)
    for record in gifts_query:
        date = int(record[1])
        index = date_series.index(date)
        parties = update_party_sums(parties, index, record[0], record[2])

    bars = []
    for i in bar_names:
        party_colour = assign_colours_to_parties(i)
        bars.append(
            go.Bar(
                name=i,
                x=date_series,
                y=parties[i],
                hovertemplate="£%{y:.4s}",
                marker_color=party_colour,
            )
        )

    # Assign colours
    gifts_graph = go.Figure(
        data=bars,
        layout={
            "xaxis": {
                "title": "",
                "dtick": 1,
            },
            "yaxis": {
                "title": "£",
                "type": "linear",
            },
            "font_family": "'Helvetica Neue', 'Open Sans', Arial",
        },
    )

    return render_template(
        "donor.html",
        title=title,
        alias=alias,
        form=form,
        gifts_graph=gifts_graph.to_json(),
    )


def update_party_sums(parties, index, party_name, value):
    if party_name in parties.keys():
        parties[party_name][index] = value
        return parties
    parties["All other parties"][index] += value
    return parties


def convert_to_js_array(query):
    """Accepts a query in the form of a list of lists. Applies escaping to the first
    column. If it's not a float, it'll wrap it in ". Returns a JS-formatted array."""
    output = ""
    for record in query:
        row = "["
        for index, cell in enumerate(record):
            if index == 0:
                cell = cell.replace('"', '\\"')
            try:
                float(cell)
            except:
                cell = '"' + str(cell) + '"'
            row += str(cell)
            if index != len(record) - 1:
                row += ", "
        row += "], "
        output += row
    output = output.rstrip(", ")
    return output


def generate_date_series(start_date, end_date):
    date_series = []
    while start_date < end_date:
        date_series.append(start_date)
        start_date += relativedelta.relativedelta(months=1)
    return date_series

@bp.route("/recipients")
def recipients():
    # Generate dates
    start_date = db.session.query(db.func.min(Donation.date)).first()[0].replace(day=1)
    end_date = db.session.query(db.func.max(Donation.date)).first()[0]
    date_series = generate_date_series(start_date, end_date)

    donation_type_filter_statements = populate_filter_statements(
        OTHER_DONATION_TYPES, "donation_type_", DonationType.name
    )
    donor_type_filter_statements = populate_filter_statements(
        OTHER_DONOR_TYPES, "donor_type_", Donor.donor_type_id
    )

    # Monthly is the smallest useful aggregation, so it's most efficient to do (and cache) 
    # that aggregation on the server, with extra binning done by Plotly
    party_stats_query = (
        db.session.query(
            Recipient.name,
            db.func.strftime("%Y-%m", Donation.date).label("month"),
            db.func.sum(Donation.value),
            Recipient.id,
        )
        .join(Recipient)
        .join(Donor)
        .join(DonationType)
        .where(db.not_(db.or_(*donation_type_filter_statements)))
        .where(db.not_(db.or_(*donor_type_filter_statements)))
        .group_by("month", Recipient.name)
        .all()
    )

    parties = {}
    for key in MAIN_PARTIES:
        parties[key] = [0] * len(date_series)

    for record in party_stats_query:
        date = dt.datetime.strptime(record[1], "%Y-%m").date()
        index = date_series.index(date)
        parties = update_party_sums(parties, index, record[0], round(record[2], 2))

    yview_args = [
        {"xbins.size": "M12"},
        {
            "xaxis.tickformat": "%Y",
            "xaxis.dtick": "M12",
            "xaxis.ticklabelmode": "period",
            "xaxis.ticks": "",
            "xaxis.tickformatstops": [],
            "xaxis.hoverformat": "%b %Y",
        },
    ]
    qview_args = [
        {"xbins.size": "M3"},
        {
            "xaxis.ticks": "outside",
            "xaxis.tickformat": "Q%q %Y",
            "xaxis.ticklabelmode": "period",
            "xaxis.dtick": "M3",
            "xaxis.tickmode": "auto",
            "xaxis.ticks": "outside",
            "xaxis.tickformatstops": [
                {"dtickrange": [None, "M5"], "value": "Q%q %Y"},
                {"dtickrange": ["M5", None], "value": "%Y"},
            ],
            "xaxis.hoverformat": "%b %Y",
        },
    ]
    mview_args = [
        {"xbins.size": "M1"},
        {
            "xaxis.tickmode": "auto",
            "xaxis.dtick": 1,
            "xaxis.ticks": "outside",
            "xaxis.ticklabelmode": "period",
            "xaxis.tickformatstops": [
                {"dtickrange": [None, "M1"], "value": "%B %Y"},
                {"dtickrange": ["M1", "M3"], "value": "Q%q %Y"},
                {"dtickrange": ["M3", None], "value": "%Y"},
            ],
        },
    ]

    figure = go.Figure(
        data=[
            go.Histogram(
                name="Conservative Party",
                customdata=["Conservative Party"] * len(date_series),
                x=date_series,
                y=parties["Conservative and Unionist Party"],
                xbins={"start": dt.datetime(2001, 1, 1), "size": "M12"},
                marker_color="rgb(0, 135, 220)",
                histfunc="sum",
                hovertemplate="£%{y:.4s}<extra>%{customdata}</extra>",
            ),
            go.Histogram(
                name="Labour Party",
                customdata=["Labour Party"] * len(date_series),
                x=date_series,
                y=parties["Labour Party"],
                xbins={"start": dt.datetime(2001, 1, 1), "size": "M12"},
                marker_color="rgb(228, 0, 59)",
                histfunc="sum",
                hovertemplate="£%{y:.4s}<extra>%{customdata}</extra>",
            ),
            go.Histogram(
                name="Liberal Democrats",
                customdata=["Liberal Democrats"] * len(date_series),
                x=date_series,
                y=parties["Liberal Democrats"],
                xbins={"start": dt.datetime(2001, 1, 1), "size": "M12"},
                marker_color="rgb(255, 159, 26)",
                histfunc="sum",
                hovertemplate="£%{y:.4s}<extra>%{customdata}</extra>",
                visible="legendonly",
            ),
            go.Histogram(
                name="Reform UK (formerly Brexit Party)",
                customdata=["Reform UK"] * len(date_series),
                x=date_series,
                y=parties["Reform UK"],
                xbins={"start": dt.datetime(2001, 1, 1), "size": "M12"},
                marker_color="rgb(0, 146, 180)",
                histfunc="sum",
                hovertemplate="£%{y:.4s}<extra>%{customdata}</extra>",
                visible="legendonly",
            ),
            go.Histogram(
                name="All other parties",
                customdata=["All other parties"] * len(date_series),
                x=date_series,
                y=parties["All other parties"],
                xbins={"start": dt.datetime(2001, 1, 1), "size": "M12"},
                marker_color="rgb(97, 224, 0)",
                histfunc="sum",
                hovertemplate="£%{y:.4s}<extra>%{customdata}</extra>",
                visible="legendonly",
            ),
        ],
        layout={
            "title": "Reportable Donations to Political Parties",
            "xaxis": {"title": "", "type": "date"},
            "xaxis_hoverformat": "%b %Y",
            "yaxis": {"title": "£", "type": "linear"},
            "sliders": [
                {
                    "active": 0,
                    "pad": {"t": 50},
                    "steps": [
                        {"args": yview_args, "label": "Year", "method": "update"},
                        {"args": qview_args, "label": "Quarter", "method": "update"},
                        {"args": mview_args, "label": "Month", "method": "update"},
                    ],
                }
            ],
            "legend": {
                "x": 0.01,
                "y": 0.99,
                "bgcolor": "rgba(255,255,255,0)",
                "bordercolor": "rgba(255,255,255,0)",
            },
            "hovermode": "x",
            "font_family": "'Helvetica Neue', 'Open Sans', Arial",
        },
    )
    figure.update_xaxes(
        tick0=dt.datetime(2001, 7, 2),
        dtick="M12",
        tickformat="%Y",
    )
    figure.update_yaxes(
        tickangle=90,
        ticklabelstep=1,
        tickformat=".2s",
    )
    figure.update_traces()

    recipient_query = (
        db.session.query(
            Recipient.name,
            Recipient.id,
            db.func.sum(Donation.value).label("donations"),
        )
        .join(Donation)
        .join(Donor)
        .join(DonationType)
        .where(db.not_(db.or_(*donation_type_filter_statements)))
        .where(db.not_(db.or_(*donor_type_filter_statements)))
        .group_by(Recipient.name)
        .order_by(db.desc("donations"))
    ).all()
    recipients = convert_to_js_array(recipient_query)

    # Response
    return render_template(
        "recipients.html",
        title="Recipients",
        figure=figure.to_json(),
        recipients=recipients,
    )


@bp.route("/donors")
def donors():
    donation_type_filter_statements = populate_filter_statements(
        OTHER_DONATION_TYPES, "donation_type_", DonationType.name
    )
    donor_type_filter_statements = populate_filter_statements(
        OTHER_DONOR_TYPES, "donor_type_", Donor.donor_type_id
    )

    top_donor_query = (
        db.session.query(
            DonorAlias.name,
            DonorAlias.id,
            Donor.donor_type_id,
            db.func.sum(Donation.value).label("donations"),
            db.func.min(Donation.date).label("first_gift"),
            db.func.max(Donation.date).label("latest_gift"),
        )
        .join(Donor, DonorAlias.id == Donor.donor_alias_id)
        .join(Donation)
        .join(DonationType)
        .where(db.not_(db.or_(*donation_type_filter_statements)))
        .where(db.not_(db.or_(*donor_type_filter_statements)))
        .group_by(DonorAlias.name)
        .order_by(db.desc("donations"))
    ).all()
    top_donors = convert_to_js_array(top_donor_query)

    top_donor_bars = [record[0] for record in top_donor_query]
    donor_type, relevant_types = assign_colours_to_donor_types(top_donor_query, 2)
    donations = [record[3] for record in top_donor_query]
    first_gift = [record[4] for record in top_donor_query]
    latest_gift = [record[5] for record in top_donor_query]

    top_donor_graph = go.Figure(
        data=[
            go.Bar(
                x=top_donor_bars,
                y=donations,
                customdata=list(zip(first_gift, latest_gift)),
                hovertemplate="£%{y:.4s}"
                "<extra>First Gift: %{customdata[0]}<br>Latest Gift: %{customdata[1]}</extra>",
                marker_color=donor_type,
                showlegend=False,
            ),
        ],
        layout={
            "title": "Biggest political donors (to all parties)",
            "xaxis": {"title": "", "range": [-0.5, 10.5]},
            "yaxis": {"title": "£", "type": "linear"},
            "legend": {
                "x": 0,
                "y": 1.02,
                "bgcolor": "rgba(255,255,255,0)",
                "bordercolor": "rgba(255,255,255,0)",
                "orientation": "h",
                "yanchor": "bottom",
            },
            "hovermode": "closest",
            "font_family": "'Helvetica Neue', 'Open Sans', Arial",
        },
    )

    for donor_type, colour in relevant_types.items():
        top_donor_graph.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                name=donor_type,
                marker_color=colour,
                line={"color": "rgba(0,0,0,0.0)"},
                marker={"size": 80},
            ),
        )

    return render_template(
        "donors.html",
        title="Donors",
        top_donor_graph=top_donor_graph.to_json(),
        top_donors=top_donors,
    )


def create_default_admin():
    user = User(username = "admin", email="admin@mailinator.com", is_admin=True)
    user.set_password("changethispassword")
    db.session.add(user)
    db.session.commit()
    flash("Default admin user registered!")
    

@bp.route("/login", methods=["GET", "POST"])
def login():
    # Default admin
    if not db.session.execute(db.select(User)).scalars().first():
        create_default_admin()
    if current_user.is_authenticated:
        flash("Already logged in!")
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(
            db.select(User).where(User.username == form.username.data)
        ).scalar()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            return redirect(url_for("main.login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        # netloc protects against attacker inserting malicious URL in "next" argument by
        # ensuring it's a relative rather than absolute URL
        if not next_page or werkzeug.urls.url_parse(next_page).netloc != "":  # pragma: no cover
            next_page = url_for("main.index")
        return redirect(next_page)
    return render_template("login.html", title="Log in", form=form)


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.index"))


@bp.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if current_user.is_authenticated and not current_user.is_admin:
        flash("Only admins can create new users")
        return redirect(url_for("main.index"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            is_admin=form.is_admin.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("New user registered!")
        return redirect(url_for("main.users"))
    return render_template("register.html", title="Register", form=form)

@bp.route("/users", methods=["GET"])
@login_required
def users():
    if current_user.is_authenticated and not current_user.is_admin:
        flash("Only admins can access the user list")
        return redirect(url_for("main.index"))
    query = db.select(User).order_by(User.id)
    users = db.session.scalars(query).all()
    return render_template(
        "users.html",
        title="Users",
        users=users,
    )


@bp.route("/users/delete/<id>", methods=["GET", "POST"])
@login_required
def delete_user(id):
    if current_user.is_authenticated and not current_user.is_admin:
        flash("Only admins can delete other users")
        return redirect(url_for("main.index"))
    if current_user.check_last_admin():
        flash("You are the last admin, so you can't delete your own account")
        return redirect(url_for("main.users"))
    user = db.get_or_404(User, id)
    title = f"Delete user: {user.username}?"
    form = DeleteUserForm()
    if form.validate_on_submit():
        db.session.execute(db.delete(User).where(User.id == user.id))
        db.session.commit()
        flash(f"User {user.username} deleted!")
        return redirect(url_for("main.users"))
    return render_template("user_delete.html", title=title, user=user, form=form)


@bp.route("/export", methods=["GET"])
@login_required
def export_data():  # pragma: no cover
    """Export all donations. Query the API, turn it into JSON and send_file it"""
    filter_string = request.query_string.decode() or DEFAULT_FILTERS
    api_url = request.url_root[:-1] + url_for("api.data") + "?" + filter_string
    data = requests.get(api_url).json()["data"]
    for record in data:
        record["date"] = dt.datetime.strptime(record["date"], "%a, %d %b %Y %H:%M:%S %Z")
        record["date"] = record["date"].strftime("%Y-%m-%d")
    filename = "donation_whistle_export_" + dt.datetime.now().strftime("%Y-%m-%d") + ".csv"
    with open("app/" + filename, "w") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=PRETTY_FIELD_NAMES.keys())
        writer.writerow(dict(PRETTY_FIELD_NAMES))
        for record in data:
            writer.writerow(record)
    return send_file(filename, as_attachment=True, mimetype="csv")

@bp.route("/notifications")
@login_required
def notifications():
    since = request.args.get("since", 0.0, type=float)
    stmt = (
        db.select(Notification)
        .where(Notification.user == current_user)
        .where(Notification.timestamp > since)
        .order_by(db.asc("timestamp"))
    )
    n = db.session.scalars(stmt).one_or_none()
    if n:
        return jsonify({"name": n.name, "data": n.get_data(), "timestamp": n.timestamp})
    else:
        return jsonify(None)
