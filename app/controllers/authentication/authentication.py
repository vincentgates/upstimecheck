from flask import render_template, Blueprint, request
from .models import *

authentication_bp = Blueprint('authentication', __name__)

# Routes with forms/authenticaton
@authentication_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        return render_template('pages/placeholder.calendar.html')

    return render_template('forms/login.html', form=form)


@authentication_bp.route('/register')
def register():
    form = RegisterForm(request.form)
    return render_template('forms/register.html', form=form)

@authentication_bp.route('/forgot')
def forgot():
    form = ForgotForm(request.form)
    return render_template('forms/forgot.html', form=form)