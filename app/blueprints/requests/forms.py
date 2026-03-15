from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, SelectMultipleField, FloatField, DateField, BooleanField, TextAreaField, HiddenField, IntegerField, DateTimeField
from wtforms.validators import DataRequired, Optional

class RequestForm(FlaskForm):
    request_number = HiddenField('Номер заявки')  # Автогенерация на бэкенде
    client_id = SelectField('Клиент', coerce=int, validators=[Optional()])
    contract_id = SelectField('Договор', coerce=int, validators=[Optional()])
    equipment_id = SelectField('Оборудование', coerce=int, validators=[Optional()])
    workers = SelectMultipleField('Исполнитель(и)', coerce=int, validators=[Optional()])
    full_name = StringField('ФИО', validators=[Optional()])
    address = StringField('Адрес', validators=[Optional()])
    phone = StringField('Телефон', validators=[Optional()])
    description = TextAreaField('Описание', validators=[DataRequired()])
    service_type = SelectField('Тип услуги', choices=[('standard', 'Стандартная'), ('warranty', 'Гарантийная'), ('emergency', 'Аварийная')], validators=[Optional()])
    type = SelectField('Тип заявки', choices=[('emergency', 'Аварийная'), ('repair', 'Ремонтная'), ('planned', 'Плановая')], validators=[Optional()])
    warranty_reason = TextAreaField('Причина гарантии', validators=[Optional()])
    urgent_price = FloatField('Срочная цена', validators=[Optional()])
    contract_regulated_price = FloatField('Сумма по регламенту', validators=[Optional()])
    materials_cost = FloatField('Стоимость материалов', validators=[Optional()])
    total_price = FloatField('Общая сумма', validators=[Optional()])
    estimated_time = IntegerField('Оценочное время (ч)', validators=[Optional()])
    planned_date = DateField('Плановая дата', validators=[DataRequired()])
    planned_start_time = DateTimeField('Плановое начало', format='%Y-%m-%d %H:%M', validators=[Optional()])
    planned_end_time = DateTimeField('Плановое окончание', format='%Y-%m-%d %H:%M', validators=[Optional()])
    status = SelectField('Статус', choices=[('pending', 'Ожидает'), ('assigned', 'Назначена'), ('closed', 'Закрыта'), ('overdue', 'Просрочена')], validators=[Optional()])
    mode = SelectField('Режим', choices=[('on_way', 'В дороге'), ('in_progress', 'В работе'), ('waiting', 'В ожидании'), ('completed', 'Выполнена'), ('normal', 'Нормальный')], validators=[Optional()])
    additional_resources_needed = BooleanField('Доп. ресурсы нужны', validators=[Optional()])
    additional_resources_reason = TextAreaField('Причина доп. ресурсов', validators=[Optional()])
    workers_count = IntegerField('Количество работников', validators=[Optional()])
    comment = TextAreaField('Комментарий', validators=[Optional()])
    submit = SubmitField('Сохранить')