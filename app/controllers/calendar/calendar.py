from flask import Blueprint, render_template, redirect, url_for, request

calendar_bp = Blueprint('calendar', __name__)


@calendar_bp.route('/cal')
def cal():
    return render_template('calendar/cal-weekly.html')