# Path: app/blueprints/photos/forms.py
# New file: Формы для загрузки, фильтров, привязки.
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Optional

class UploadForm(FlaskForm):
    file = FileField('Файл', validators=[DataRequired(), FileAllowed(['jpg', 'png', 'jpeg', 'gif', 'mp4', 'pdf'], 'Только изображения, видео или PDF!')])
    description = StringField('Описание', validators=[Optional()])
    category = SelectField('Категория', choices=[('', 'Не указано'), ('equipment', 'Оборудование'), ('works', 'Работы'), ('documents', 'Документы')], validators=[Optional()])
    client_id = HiddenField('Клиент ID', validators=[Optional()])
    request_id = HiddenField('Заявка ID', validators=[Optional()])
    equipment_id = HiddenField('Оборудование ID', validators=[Optional()])
    submit = SubmitField('Загрузить')

class FilterForm(FlaskForm):
    date_from = StringField('Дата от (YYYY-MM-DD)', validators=[Optional()])
    date_to = StringField('Дата до (YYYY-MM-DD)', validators=[Optional()])
    client = StringField('Клиент', validators=[Optional()])
    author = StringField('Автор', validators=[Optional()])
    category = SelectField('Категория', choices=[('', 'Все'), ('equipment', 'Оборудование'), ('works', 'Работы'), ('documents', 'Документы')], validators=[Optional()])
    submit = SubmitField('Фильтровать')

class AttachForm(FlaskForm):
    media_id = HiddenField('Media ID', validators=[DataRequired()])
    entity_type = SelectField('Привязать к', choices=[('client', 'Клиент'), ('request', 'Заявка'), ('equipment', 'Оборудование')], validators=[DataRequired()])
    entity_id = StringField('ID сущности', validators=[DataRequired()])
    submit = SubmitField('Привязать')