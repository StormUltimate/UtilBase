# Path: app/blueprints/map/forms.py
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, StringField
from wtforms.validators import Optional

class MapFilterForm(FlaskForm):
    filter_type = SelectField(
        'Показывать',
        choices=[('all', 'Клиенты и заявки'), ('clients', 'Только клиенты'), ('requests', 'Только заявки')],
        validators=[Optional()]
    )
    client_search = StringField('Клиент (ФИО / адрес / телефон)', validators=[Optional()])
    request_search = StringField('Заявка (номер / текст)', validators=[Optional()])
    submit = SubmitField('Применить')