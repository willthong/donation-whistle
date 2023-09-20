from flask import flash, redirect, request, render_template, url_for
from flask_login import login_required

from app import db
from app.alias import bp
from app.alias.forms import DeleteAlias, NewAliasName
from app.models import Donor, DonorAlias

@bp.route("/aliases", methods=["GET"])
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


@bp.route("/create_new", methods=["GET", "POST"])
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


@bp.route("/new", methods=["GET", "POST"])
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
        if (
            alias and 
            form.alias_name.data not in [d.name for d in selected_donors] and 
            Donor.query.filter_by(name=form.alias_name.data).first()
        ):
            # Only add a new alias if donors includes a donor with the proposed name, otherwise
            # it'll be orphaning a different donor.
            flash("That alias name is already taken.")
            return redirect(
                url_for(
                    "alias.new_alias",
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
        return redirect(url_for("alias.aliases"))
    return render_template(
        "new_alias_name.html",
        title="New alias creation",
        selected_donors=selected_donors,
        form=form,
    )


@bp.route("/<id>", methods=["GET", "POST"])
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
            return redirect(url_for("alias.aliases", id=id))
        alias.name = form.alias_name.data or None
        alias.note = form.note.data or None
        db.session.commit()
        flash("Alias updated!")
    return render_template("alias_detail.html", title=title, alias=alias, form=form)


@bp.route("/delete/<id>", methods=["GET", "POST"])
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
        return redirect(url_for("alias.aliases"))
    return render_template("alias_delete.html", title=title, alias=alias, form=form)


@bp.route("/delete/<alias_id>/<donor_id>", methods=["GET", "POST"])
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
        return redirect(url_for("alias.aliases"))
    return render_template(
        "alias_remove.html",
        title=title,
        alias=alias,
        donor=donor,
        form=form,
        full_delete=full_delete,
    )
