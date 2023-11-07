from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileRequired
from wtforms import FileField, StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError

# File size validator
def FileSizeLimit(max_size_in_mb): #pragma: no cover
    max_bytes = max_size_in_mb * 1024 * 1024

    def file_length_check(form, field):
        if len(field.data.read()) > max_bytes:
            raise ValidationError(f"File size must be less than {max_size_in_mb}MB")
        field.data.seek(0)

    return file_length_check


class NewAliasName(FlaskForm):
    alias_name = StringField("New alias name", validators=[DataRequired()])
    note = StringField("Notes")
    submit = SubmitField("Save alias")
    
class DeleteAlias(FlaskForm):
    submit = SubmitField("Confirm alias deletion")
    
class JSONForm(FlaskForm):
    json = FileField(
        validators=[
            FileRequired(),
            FileAllowed(["json"]),
            FileSizeLimit(max_size_in_mb=1),
        ]
    )


