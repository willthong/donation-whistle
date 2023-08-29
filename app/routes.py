from werkzeug.urls import url_parse

from flask import flash, redirect, request, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import (
    DataRequired,
)

from app import app, db
from app.models import User, DonorAlias, Donor, Donation
from app.forms import (
    LoginForm,
    RegistrationForm,
    NewAliasName,
    DeleteAlias,
)


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Sign In")


@app.route("/")
@app.route("/index")
def index():
    return render_template("index.html", title="Home")


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
    print(query)
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
        print(alias)
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
