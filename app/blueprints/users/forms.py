# Path: app/blueprints/users/forms.py
from flask_wtf import FlaskForm
from wtforms import IntegerField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class LoginForm(FlaskForm):
    username = StringField("Имя пользователя", validators=[DataRequired()])
    password = PasswordField("Пароль", validators=[DataRequired()])
    submit = SubmitField("Войти")


class UserForm(FlaskForm):
    username = StringField("Имя пользователя", validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField("Пароль", validators=[Optional(), Length(min=4, max=128)])
    full_name = StringField("ФИО", validators=[Optional(), Length(max=255)])
    phone = StringField("Телефон", validators=[Optional(), Length(max=64)])
    role = SelectField(
        "Роль",
        choices=[
            ("admin", "Admin"),
            ("dispatcher", "Dispatcher"),
            ("engineer", "Engineer"),
            ("master", "Master"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Сохранить")


class UserDeleteForm(FlaskForm):
    user_id = IntegerField("ID пользователя", validators=[DataRequired()])
    submit = SubmitField("Удалить")
