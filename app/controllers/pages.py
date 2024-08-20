from flask import render_template, Blueprint, request

blueprint = Blueprint('pages', __name__)

# Dictionary mapping routes to their corresponding placeholder templates
app_placeholder = {
    "/": "home", #also moving to it's own module
    "/features": "features",
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