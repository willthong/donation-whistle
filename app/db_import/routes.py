from flask import current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from datetime import datetime
import glob
import re

from app.db_import import bp
from app.db_import.forms import DBImport


def last_download():
    """Finds last downloaded date"""
    raw_data_file = glob.glob("raw_data_*.csv", root_dir="./db/")
    try:
        last_download = re.findall(r"\d{4}\-\d{2}\-\d{2}", raw_data_file[0])
        last_download = datetime.strptime(last_download[0], "%Y-%m-%d")
        last_download = last_download.strftime("%d %B %Y")
    except:  # pragma: no cover
        last_download = None
    return last_download


@bp.route("/dl_and_import", methods=["GET", "POST"])
@login_required
def dl_and_import():
    form = DBImport()
    if not form.validate_on_submit():
        return render_template(
            "db_import.html", form=form, last_download=last_download()
        )
    if current_user.get_task_in_progress():  # pragma: no cover
        flash("A database import is currently in progress.")
        return redirect(url_for("main.index"))
    current_user.launch_task()  # pragma: no cover
    return redirect(url_for("main.index"))  # pragma: no cover
