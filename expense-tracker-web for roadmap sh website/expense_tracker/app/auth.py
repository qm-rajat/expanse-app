from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from .models import create_user, find_user_by_username, verify_password
from flask_mail import Mail, Message
import random, time
import logging
import traceback

auth = Blueprint('auth', __name__)
mail = Mail()

def send_2fa_code(email, code, username):
    try:
        msg = Message('🔐 Your Expense Tracker Pro Verification Code', recipients=[email])
        
        # Render the HTML template with the verification code
        html_content = render_template('email_verification.html', 
                                     verification_code=code, 
                                     username=username,
                                     email=email)
        
        msg.html = html_content
        msg.body = f'Your verification code is: {code}'
        
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending 2FA email: {e}")
        traceback.print_exc()
        return False

@auth.record_once
def on_load(state):
    mail.init_app(state.app)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember_me = request.form.get('remember_me') == 'on'
        
        user = find_user_by_username(username)
        if user and verify_password(user['password'], password):
            if remember_me:
                # Skip 2FA for "Remember Me" option
                session['user_id'] = str(user['_id'])
                session['username'] = user['username']
                session['remember_me'] = True
                session['login_time'] = int(time.time())
                flash('Logged in successfully!')
                return redirect(url_for('main.index'))
            else:
                # Generate 2FA code for regular login
                code = str(random.randint(100000, 999999))
                session['2fa_code'] = code
                session['2fa_expiry'] = int(time.time()) + 300
                session['2fa_user_id'] = str(user['_id'])
                session['2fa_username'] = user['username']
                session['2fa_email'] = user['email']
                if send_2fa_code(user['email'], code, user['username']):
                    flash('A verification code has been sent to your email.')
                    return redirect(url_for('auth.verify_2fa'))
                else:
                    flash('Failed to send verification code. Please try again.')
                    return redirect(url_for('auth.login'))
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

@auth.route('/verify', methods=['GET', 'POST'])
def verify_2fa():
    if '2fa_code' not in session:
        return redirect(url_for('auth.login'))
    if request.method == 'POST':
        code = request.form['code']
        if code == session.get('2fa_code') and int(time.time()) < session.get('2fa_expiry', 0):
            session['user_id'] = session['2fa_user_id']
            session['username'] = session['2fa_username']
            # Clean up 2FA session
            session.pop('2fa_code', None)
            session.pop('2fa_expiry', None)
            session.pop('2fa_user_id', None)
            session.pop('2fa_username', None)
            session.pop('2fa_email', None)
            flash('Logged in successfully!')
            return redirect(url_for('main.index'))
        else:
            flash('Invalid or expired code.')
    return render_template('verify_2fa.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if find_user_by_username(username):
            flash('Username already exists.')
        else:
            result = create_user(username, email, password)
            if result is not None and hasattr(result, 'inserted_id'):
                flash('Registration successful! Please log in.')
                return redirect(url_for('auth.login'))
            else:
                flash('Registration failed due to a database error. Please try again or contact support.')
    return render_template('register.html')

@auth.route('/logout')
def logout():
    # Clear all session data including "Remember Me" data
    session.clear()
    flash('Logged out successfully!')
    return redirect(url_for('auth.login'))

 