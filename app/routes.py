from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from plotly import graph_objects as go
from werkzeug.urls import url_parse

from flask import flash, jsonify, redirect, request, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (
    DataRequired,
)

from app import app, db, cache
from app.models import (
    User,
    DonorAlias,
    Donor,
    Donation,
    Recipient,
    DonationType,
)
from app.forms import (
    LoginForm,
    RegistrationForm,
    NewAliasName,
    DeleteAlias,
    FilterForm,
)

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

DONOR_TYPE_COLOURS = {
    "Individual": "indigo",
    "Company": "slateblue",
    "Limited Liability Partnership": "seagreen",
    "Trade Union": "hotpink",
    "Unincorporated Association": "yellow",
}


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Sign In")


@app.route("/", methods=["GET", "POST"])
@app.route("/index", methods=["GET", "POST"])
def index():
    form = FilterForm()

    if form.validate_on_submit():
        filter_list = [par for par in request.form.keys() if request.form[par] == "y"]
        if request.form["date_gt"]:
            filter_list.append("date_gt_" + request.form["date_gt"])
        if request.form["date_lt"]:
            filter_list.append("date_lt_" + request.form["date_lt"])
        return redirect(
            url_for(
                "index",
                filter=filter_list,
            )
        )
    # The api_filter parameter will be appended to the API URL by the template
    filter_string = request.query_string.decode()
    if not filter_string:
        filter_string = DEFAULT_FILTERS
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


@app.route("/api/data")
@cache.cached(timeout=600000, query_string=True)
# https://stackoverflow.com/a/47181782
def data():
    query = db.select(Donation).join(Recipient).join(Donor).join(DonationType)

    # Filtering
    # Multiple identically named keys => weird dictionary-like object to which we must
    # apply .getlist() rather than looping through as we would a normal dict
    # https://tedboy.github.io/flask/generated/generated/werkzeug.MultiDict.html)
    all_filters = request.args.getlist("filter")

    # Populate filter types
    recipient_filters = []
    donor_type_filters = []
    donation_type_filters = []
    is_legacy_filters = []
    start_date_filter = None
    end_date_filter = None

    for filter in all_filters:
        if filter.startswith("recipient"):
            recipient_filters.append(filter)
        if filter == "donor_type_other":
            donor_type_filters.extend(OTHER_DONOR_TYPES)
        if filter.startswith("donor_type"):
            donor_type_filters.append(filter)
        if filter.startswith("donation_type"):
            donation_type_filters.append(filter)
        if filter == "donation_type_other":
            donation_type_filters.extend(OTHER_DONATION_TYPES)
        if filter.startswith("is_legacy"):
            is_legacy_filters.append(filter)
        if filter.startswith("date_gt_"):
            start_date_filter = datetime.strptime(filter[-10:], "%Y-%m-%d")
        if filter.startswith("date_lt_"):
            end_date_filter = datetime.strptime(filter[-10:], "%Y-%m-%d")

    # Each filter bucket is an additional group of ORs added as an AND, so need to be grouped together
    recipient_filter_statements = populate_filter_statements(
        recipient_filters, "recipient_", Recipient.name
    )
    donor_type_filter_statements = populate_filter_statements(
        donor_type_filters, "donor_type_", Donor.donor_type_id
    )
    donation_type_filter_statements = populate_filter_statements(
        donation_type_filters, "donation_type_", DonationType.name
    )

    if recipient_filter_statements and "recipient_other" in all_filters:
        query = query.where(
            db.or_(
                db.not_(
                    db.or_(
                        Recipient.name == "Labour Party",
                        Recipient.name == "Conservative and Unionist Party",
                        Recipient.name == "Liberal Democrats",
                        Recipient.name == "Scottish National Party (SNP)",
                        Recipient.name == "Green Party",
                        Recipient.name == "Reform UK",
                    )
                ),
                (db.or_(*recipient_filter_statements)),
            )
        )
    elif recipient_filter_statements:
        query = query.where(db.or_(*recipient_filter_statements))
    if donor_type_filter_statements:
        query = query.where(db.or_(*donor_type_filter_statements))
    if donation_type_filter_statements:
        query = query.where(db.or_(*donation_type_filter_statements))
    if "is_legacy_false" in is_legacy_filters and "is_legacy_true" in is_legacy_filters:
        pass
    elif "is_legacy_false" in is_legacy_filters:
        query = query.where(Donation.is_legacy == False)
    elif "is_legacy_true" in is_legacy_filters:
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
        query = query.where(
            Donor.name.ilike(f"%{search}%"),
        )
    total = len(list(db.session.scalars(query)))

    # Sorting
    sort = request.args.get("sort")
    if sort:
        for s in sort.split(","):
            direction = s[0]
            criterion = s[1:]
            criterion_lookups = {
                "donor": Donor.name,
                "recipient": Recipient.name,
                "date": Donation.date,
                "value": Donation.value,
            }
            if criterion in criterion_lookups:
                criterion = criterion_lookups[criterion]
            else:
                criterion = "Donation.date"
            if direction == "-":
                query = query.order_by(criterion.desc())
            else:
                query = query.order_by(criterion)

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


def apply_date_filters(query, all_filters):
    for filter in all_filters:
        if filter.startswith("date_gt_"):
            query = query.where(
                Donation.date >= datetime.strptime(filter[-10:], "%Y-%m-%d")
            )
        if filter.startswith("date_lt_"):
            query = query.where(
                Donation.date <= datetime.strptime(filter[-10:], "%Y-%m-%d")
            )
    return query


@app.route("/recipient/<int:id>", methods=["GET", "POST"])
def recipient(id):
    recipient = db.get_or_404(Recipient, id)
    title = recipient.name

    form = FilterForm()

    if form.validate_on_submit():
        filter_list = []
        if request.form["date_gt"]:
            filter_list.append("date_gt_" + request.form["date_gt"])
        if request.form["date_lt"]:
            filter_list.append("date_lt_" + request.form["date_lt"])
        return redirect(
            url_for(
                "recipient",
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
    donor_type, relevant_types = [], {}
    for record in top_donor_query:
        if record[1] in DONOR_TYPE_COLOURS:
            donor_type.append(DONOR_TYPE_COLOURS[record[1]])
            if DONOR_TYPE_COLOURS[record[1]] not in relevant_types:
                relevant_types[record[1]] = DONOR_TYPE_COLOURS[record[1]]
        else:
            donor_type.append("black")
            if "Other" not in relevant_types:
                relevant_types["Other"] = "black"
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
    donor_type, relevant_types = [], {}
    for record in donation_sources_query:
        if record[0] in DONOR_TYPE_COLOURS:
            donor_type.append(DONOR_TYPE_COLOURS[record[0]])
            if DONOR_TYPE_COLOURS[record[0]] not in relevant_types:
                relevant_types[record[0]] = DONOR_TYPE_COLOURS[record[0]]
        else:
            donor_type.append("black")
            if "Other" not in relevant_types:
                relevant_types["Other"] = "black"

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
        },
    )
    donation_sources_graph.update_yaxes(
        range=(-0.5, 2.5), constrain="domain", ticksuffix=" "
    )

    return render_template(
        "recipient.html",
        title=title,
        recipient=recipient,
        top_donor_graph=top_donor_graph.to_json(),
        donation_sources_graph=donation_sources_graph.to_json(),
        form=form,
    )


@app.route("/stats/recipients")
def recipient_stats():
    # Generate dates
    start_date = db.session.query(db.func.min(Donation.date)).first()[0].replace(day=1)
    end_date = db.session.query(db.func.max(Donation.date)).first()[0]
    date_series = []
    while start_date < end_date:
        date_series.append(start_date)
        start_date += relativedelta(months=1)

    donation_type_filter_statements = populate_filter_statements(
        OTHER_DONATION_TYPES, "donation_type_", DonationType.name
    )
    donor_type_filter_statements = populate_filter_statements(
        OTHER_DONOR_TYPES, "donor_type_", Donor.donor_type_id
    )

    # Monthly is the smallest useful aggregation, so it's most
    # efficient to do (and cache) that aggregation on the server, with extra binning
    # done by Plotly
    # Donor still required in order to filter donor types
    query = (
        db.session.query(
            Recipient.name,
            db.func.strftime("%Y-%m", Donation.date).label("month"),
            db.func.sum(Donation.value),
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

    parties["Conservative and Unionist Party"] = [0 for i in range(0, len(date_series))]
    parties["Labour Party"] = [0 for i in range(0, len(date_series))]
    parties["Liberal Democrats"] = [0 for i in range(0, len(date_series))]
    parties["Reform UK"] = [0 for i in range(0, len(date_series))]
    parties["All other parties"] = [0 for i in range(0, len(date_series))]

    for record in query:
        date = datetime.strptime(record[1], "%Y-%m").date()
        index = date_series.index(date)
        if record[0] not in [
            "Conservative and Unionist Party",
            "Labour Party",
            "Liberal Democrats",
            "Reform UK",
        ]:
            parties["All other parties"][index] += round(record[2], 2)
        else:
            parties[record[0]][index] = round(record[2], 2)

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
                customdata=["Conservative Party" for value in date_series],
                x=date_series,
                y=parties["Conservative and Unionist Party"],
                xbins={"start": datetime(2001, 1, 1), "size": "M12"},
                marker_color="rgb(0, 135, 220)",
                histfunc="sum",
                hovertemplate="£%{y:.4s}<extra>%{customdata}</extra>",
            ),
            go.Histogram(
                name="Labour Party",
                customdata=["Labour Party" for value in date_series],
                x=date_series,
                y=parties["Labour Party"],
                xbins={"start": datetime(2001, 1, 1), "size": "M12"},
                marker_color="rgb(228, 0, 59)",
                histfunc="sum",
                hovertemplate="£%{y:.4s}<extra>%{customdata}</extra>",
            ),
            go.Histogram(
                name="Liberal Democrats",
                customdata=["Liberal Democrats" for value in date_series],
                x=date_series,
                y=parties["Liberal Democrats"],
                xbins={"start": datetime(2001, 1, 1), "size": "M12"},
                marker_color="rgb(255, 159, 26)",
                histfunc="sum",
                hovertemplate="£%{y:.4s}<extra>%{customdata}</extra>",
                visible="legendonly",
            ),
            go.Histogram(
                name="Reform UK (formerly Brexit Party)",
                customdata=["Reform UK" for value in date_series],
                x=date_series,
                y=parties["Reform UK"],
                xbins={"start": datetime(2001, 1, 1), "size": "M12"},
                marker_color="rgb(0, 146, 180)",
                histfunc="sum",
                hovertemplate="£%{y:.4s}<extra>%{customdata}</extra>",
                visible="legendonly",
            ),
            go.Histogram(
                name="All other parties",
                customdata=["All other parties" for value in date_series],
                x=date_series,
                y=parties["All other parties"],
                xbins={"start": datetime(2001, 1, 1), "size": "M12"},
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
        },
    )
    figure.update_xaxes(
        tick0=datetime(2001, 7, 2),
        dtick="M12",
        tickformat="%Y",
    )
    figure.update_yaxes(
        tickangle=90,
        ticklabelstep=1,
        tickformat=".2s",
    )
    figure.update_traces()

    # Categories can be facetted subplots?

    # Response
    return render_template(
        "recipient_stats.html", title="Party statistics", figure=figure.to_json()
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(
            db.select(User).where(User.username == form.username.data)
        ).scalar()
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password")
            return redirect(url_for("login"))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get("next")
        # netloc protects against attacker inserting malicious URL in "next" argument by
        # ensuring it's a relative rather than absolute URL
        if not next_page or url_parse(next_page).netloc != "":
            next_page = url_for("index")
        return redirect(next_page)
    return render_template("login.html", title="Log in", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
@login_required
def register():
    if current_user.is_authenticated and not current_user.is_admin:
        flash("Only admins can create new users")
        return redirect(url_for("index"))
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
        # TODO: change this to the admin's users panel
        return redirect(url_for("login"))
    return render_template("register.html", title="Register", form=form)


# To protect a function with login, add the @login_required decorator between the
# @app.route function and the function definition


@app.route("/aliases", methods=["GET"])
def aliases():
    query = (
        db.select(DonorAlias)
        .join(DonorAlias.donors)
        .group_by(DonorAlias)
        .having(db.func.count(DonorAlias.donors) > 1)
        .order_by(DonorAlias.name)
    )
    grouped_aliases = db.session.scalars(query).all()
    query = (
        db.select(DonorAlias)
        .join(DonorAlias.donors)
        .group_by(DonorAlias)
        .having(db.func.count(DonorAlias.donors) == 1)
        .order_by(DonorAlias.name)
    )
    ungrouped_aliases = db.session.scalars(query).all()
    return render_template(
        "aliases.html",
        title="Aliases",
        grouped_aliases=grouped_aliases,
        ungrouped_aliases=ungrouped_aliases,
    )


@app.route("/create_new_alias", methods=["GET", "POST"])
@login_required
def create_new_alias():
    query = (
        db.select(DonorAlias)
        .join(DonorAlias.donors)
        .group_by(DonorAlias)
        .having(db.func.count(DonorAlias.donors) == 1)
        .order_by(DonorAlias.name)
    )
    ungrouped_aliases = db.session.scalars(query).all()
    return render_template(
        "create_new_alias.html",
        title="Create a new alias",
        ungrouped_aliases=ungrouped_aliases,
    )


@app.route("/new_alias", methods=["GET", "POST"])
@login_required
def new_alias():
    form = NewAliasName()
    selected_donors = []
    selected_donor_ids = (
        request.args.get("selected_donors").replace('"', "").strip("[]").split(",")
    )
    for id in selected_donor_ids:
        if Donor.query.filter_by(donor_alias_id=id).first():
            selected_donors.append(Donor.query.filter_by(donor_alias_id=id).first())

    if form.validate_on_submit():
        query = db.select(DonorAlias).filter_by(name=form.alias_name.data)
        alias = db.session.execute(query).scalars().first()
        if alias and form.alias_name.data not in [d.name for d in selected_donors]:
            # Only add a new alias if donors includes a donor with the proposed name, otherwise
            # it'll be orphaning a different donor.
            flash("That alias name is already taken.")
            return redirect(
                url_for(
                    "new_alias_name",
                    selected_donors=request.args.get("selected_donors"),
                )
            )
            # TODO: fix the bug where you try to use a new alias name which corresponds
            # to an existing alias
        alias = DonorAlias(
            name=form.alias_name.data,
            note=form.note.data,
            donors=selected_donors,
        )
        db.session.add(alias)
        db.session.commit()
        flash("New donor alias added!")
        return redirect(url_for("aliases"))
    return render_template(
        "new_alias_name.html",
        title="New alias creation",
        selected_donors=selected_donors,
        form=form,
    )


@app.route("/alias/<id>", methods=["GET", "POST"])
@login_required
def alias(id):
    alias = db.get_or_404(DonorAlias, id)
    title = f"Alias detail: {alias.name}"
    form = NewAliasName()
    if form.validate_on_submit():
        query = db.select(DonorAlias).filter_by(name=form.alias_name.data)
        dupe_alias = db.session.execute(query).scalars().first()
        if dupe_alias and form.alias_name.data not in [d.name for d in alias.donors]:
            # Only add a new alias if donors includes a donor with the proposed name, otherwise
            # it'll be orphaning a different donor.
            flash("That alias name is already taken.")
            return redirect(url_for("alias", id=id))
        alias.name = form.alias_name.data or None
        alias.note = form.note.data or None
        db.session.commit()
        flash("Alias updated!")
    return render_template("alias_detail.html", title=title, alias=alias, form=form)


@app.route("/alias/delete/<id>", methods=["GET", "POST"])
@login_required
def delete_alias(id):
    alias = db.get_or_404(DonorAlias, id)
    title = f"Delete alias: {alias.name}?"
    form = DeleteAlias()
    if form.validate_on_submit():
        # Re-create aliases for donors linked to the alias so they are not orphaned
        for donor in alias.donors:
            new_alias = DonorAlias(name=donor.name)
            new_alias.donors.append(donor)
            db.session.add(new_alias)
        # No need to delete the alias, because the last donor left will have its own alias
        db.session.commit()
        flash(f"Alias {alias.name} deleted!")
        return redirect(url_for("aliases"))
    return render_template("alias_delete.html", title=title, alias=alias, form=form)


@app.route("/alias/delete/<alias_id>/<donor_id>", methods=["GET", "POST"])
@login_required
def remove_alias(alias_id, donor_id):
    alias = db.get_or_404(DonorAlias, alias_id)
    donor = db.get_or_404(Donor, donor_id)
    title = f"Remove {donor.name} from {alias.name}??"
    form = DeleteAlias()
    full_delete = True if (alias.name == donor.name) else False
    if form.validate_on_submit():
        if full_delete:
            for donor in alias.donors:
                new_alias = DonorAlias(name=donor.name)
                new_alias.donors.append(donor)
                db.session.add(new_alias)
            flash(f"{alias.name} deleted!")
        else:
            alias.donors.remove(donor)
            new_alias = DonorAlias(name=donor.name)
            new_alias.donors.append(donor)
            db.session.add(new_alias)
            flash(f"Donor {donor.name} removed from alias {alias.name}!")
        db.session.commit()
        return redirect(url_for("aliases"))
    return render_template(
        "alias_remove.html",
        title=title,
        alias=alias,
        donor=donor,
        form=form,
        full_delete=full_delete,
    )
