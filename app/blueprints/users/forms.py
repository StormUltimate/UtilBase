# Path: app/blueprints/users/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Optional, Length

class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')

class UserForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=4, max=20)])
    password = PasswordField('Пароль', validators=[DataRequired()])
    role = SelectField('Роль', choices=[('admin', 'Admin'), ('engineer', 'Engineer'), ('master', 'Master')], validators=[DataRequired()])
    submit = SubmitField('Сохранить')

class UserDeleteForm(FlaskForm):
    user_id = IntegerField('ID пользователя', validators=[DataRequired()])
    submit = SubmitField('Удалить')