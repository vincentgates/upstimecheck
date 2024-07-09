from flask import render_template, Blueprint, request
from app.forms import *

blueprint = Blueprint('pages', __name__)

# Dictionary mapping routes to their corresponding placeholder templates
app_placeholder = {
    "/": "home",
    "/features": "features",
    "/cal": "calendar",
    "/faq": "faq",
}

# Helper function to create a route function with a unique endpoint
def create_route(template_path):
    def route():
        return render_template(template_path)
    return route

# Routes created dynamically looping through the dictionary
for route, name in app_placeholder.items():
    template_path = f'pages/placeholder.{name}.html'
    blueprint.add_url_rule(route, endpoint=f"pages_{name}", view_func=create_route(template_path))

# Routes with forms
@blueprint.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(request.form)
    if request.method == 'POST' and form.validate():
        return render_template('pages/placeholder.calendar.html')

    return render_template('forms/login.html', form=form)


@blueprint.route('/register')
def register():
    form = RegisterForm(request.form)
    return render_template('forms/register.html', form=form)

@blueprint.route('/forgot')
def forgot():
    form = ForgotForm(request.form)
    return render_template('forms/forgot.html', form=form)
