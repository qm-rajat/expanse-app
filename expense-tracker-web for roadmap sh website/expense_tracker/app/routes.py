from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, jsonify
from .models import get_expenses, add_expense, update_expense, delete_expense, get_expense_by_id, CATEGORIES, add_recurring_expense, get_recurring_expenses, process_recurring_expenses, add_budget, get_budgets, update_budget, delete_budget, get_budget_for_category, create_group, join_group, get_user_groups, get_group_by_id, find_user_by_username, verify_password, add_comment, get_approved_comments, get_all_comments, approve_comment, delete_comment, get_mongo
from datetime import datetime, timedelta
from functools import wraps
from .utils import export_expenses_csv, export_expenses_pdf, convert_currency, ExpenseValidator, UserValidator, ValidationResult, check_session_expiry
import pytesseract
from collections import Counter
from PIL import Image
import os
from collections import defaultdict
import pandas as pd
from flask_bcrypt import generate_password_hash
from bson.objectid import ObjectId
from dateutil.relativedelta import relativedelta

main = Blueprint('main', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_session_expiry():
            flash('Please log in to access this page.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@main.route('/')
@login_required
def index():
    user_id = session['user_id']
    process_recurring_expenses(user_id)
    # Smart suggestions
    now = datetime.now()
    this_month = now.strftime('%Y-%m')
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    expenses = get_expenses(user_id=user_id)
    cat_this = defaultdict(float)
    cat_last = defaultdict(float)
    for e in expenses:
        if e.get('type') == 'expense':
            month = e.get('date', '')[:7]
            if month == this_month:
                cat_this[e.get('category', 'Other')] += e.get('amount', 0)
            elif month == last_month:
                cat_last[e.get('category', 'Other')] += e.get('amount', 0)
    suggestions = []
    for cat in cat_this:
        if cat_this[cat] > 0 and cat_last[cat] > 0:
            change = (cat_this[cat] - cat_last[cat]) / cat_last[cat]
            if change > 0.2:
                suggestions.append(f"You spent {int(change*100)}% more on {cat} this month. Consider ways to save!")
            elif change < -0.2:
                suggestions.append(f"Great job! You spent {abs(int(change*100))}% less on {cat} this month.")
    if not suggestions:
        suggestions.append("Keep tracking your expenses for personalized tips!")
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    currency = request.args.get('currency', 'INR')
    group_id = request.args.get('group_id')
    expenses = get_expenses(
        user_id=user_id if not group_id else None,
        category=category if category else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None
    )
    if group_id:
        expenses = [e for e in expenses if str(e.get('group_id')) == group_id]
    for e in expenses:
        exp_curr = e.get('currency', 'INR')
        e['amount'] = convert_currency(e['amount'], exp_curr, currency)
    total_income = sum(e['amount'] for e in expenses if e.get('type') == 'income')
    total_expenses = sum(e['amount'] for e in expenses if e.get('type') == 'expense')
    balance = total_income - total_expenses
    summary = {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'balance': balance,
        'currency': currency
    }
    # Budgets and progress
    budgets = get_budgets(user_id)
    budget_progress = []
    for b in budgets:
        spent = sum(e['amount'] for e in expenses if e.get('category') == b['category'] and e.get('type') == 'expense')
        percent = int((spent / b['amount']) * 100) if b['amount'] > 0 else 0
        alert = percent >= 90
        over = percent > 100
        budget_progress.append({'category': b['category'], 'amount': b['amount'], 'spent': spent, 'percent': percent, 'alert': alert, 'over': over})
    # Chart data
    cat_counter = Counter()
    for e in expenses:
        if e.get('type') == 'expense':
            cat_counter[e.get('category', 'Other')] += e.get('amount', 0)
    pie_labels = list(cat_counter.keys())
    pie_data = list(cat_counter.values())
    date_counter = defaultdict(float)
    for e in expenses:
        if e.get('type') == 'expense':
            date_counter[e.get('date', '')] += e.get('amount', 0)
    bar_labels = sorted(date_counter.keys())
    bar_data = [date_counter[d] for d in bar_labels]
    
    # Ensure chart data is always valid
    chart_data = {
        'pie_labels': pie_labels if pie_labels else ['No Data'],
        'pie_data': pie_data if pie_data else [0],
        'bar_labels': bar_labels if bar_labels else ['No Data'],
        'bar_data': bar_data if bar_data else [0]
    }
    
    # Calculate additional dashboard insights
    top_category = None
    biggest_expense = None
    savings_rate = None
    
    if cat_counter:
        top_category = max(cat_counter, key=cat_counter.get)
    
    if expenses:
        expense_items = [e for e in expenses if e.get('type') == 'expense']
        if expense_items:
            biggest_expense_item = max(expense_items, key=lambda x: x.get('amount', 0))
            biggest_expense = f"{biggest_expense_item.get('category', 'Unknown')} - {biggest_expense_item.get('amount', 0):.2f} {currency}"
    
    if total_income > 0:
        savings_rate = f"{((total_income - total_expenses) / total_income * 100):.1f}%"
    currencies = ['INR', 'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD']
    user_groups = get_user_groups(user_id)
    # Reminder message for due recurring expenses
    recs = get_recurring_expenses(user_id)
    today = datetime.now().date().isoformat()
    reminder_message = None
    for rec in recs:
        if rec['next_date'] == today:
            reminder_message = f"Recurring expense '{rec['description']}' is due today!"
            break
    # --- New Analysis Data for Dashboard ---
    # 1. Monthly Expense Trend (last 12 months)
    months = []
    monthly_expenses = []
    monthly_income = []
    monthly_savings_rate = []
    now_month = now.replace(day=1)
    for i in range(11, -1, -1):
        month = (now_month - relativedelta(months=i)).strftime('%Y-%m')
        months.append(month)
        exp = sum(e['amount'] for e in expenses if e.get('type') == 'expense' and e.get('date', '')[:7] == month)
        inc = sum(e['amount'] for e in expenses if e.get('type') == 'income' and e.get('date', '')[:7] == month)
        monthly_expenses.append(exp)
        monthly_income.append(inc)
        if inc > 0:
            monthly_savings_rate.append(round((inc - exp) / inc * 100, 1))
        else:
            monthly_savings_rate.append(0)
    # 2. Top Categories (last 12 months)
    cat_counter_12mo = Counter()
    for e in expenses:
        if e.get('type') == 'expense' and e.get('date', '')[:7] in months:
            cat_counter_12mo[e.get('category', 'Other')] += e.get('amount', 0)
    top_categories = cat_counter_12mo.most_common(5)
    top_cat_labels = [c[0] for c in top_categories]
    top_cat_data = [c[1] for c in top_categories]
    # 3. Biggest Single Expenses (last 12 months)
    biggest_expenses = sorted(
        [e for e in expenses if e.get('type') == 'expense' and e.get('date', '')[:7] in months],
        key=lambda x: x.get('amount', 0), reverse=True)[:5]
    # --- End New Analysis Data ---
    # --- New Cool Graphs Data ---
    # 1. Stacked Bar Chart: Monthly expenses by category
    months_set = set(months)
    all_categories = sorted({e.get('category', 'Other') for e in expenses if e.get('type') == 'expense'})
    monthly_category_expenses = {cat: [0]*len(months) for cat in all_categories}
    for idx, month in enumerate(months):
        for cat in all_categories:
            monthly_category_expenses[cat][idx] = sum(
                e['amount'] for e in expenses if e.get('type') == 'expense' and e.get('category') == cat and e.get('date', '')[:7] == month
            )
    stacked_bar_data = {
        'labels': months,
        'datasets': [
            {'label': cat, 'data': monthly_category_expenses[cat]} for cat in all_categories
        ]
    }
    # 2. Horizontal Bar Chart: Top 10 largest expenses
    top_expenses = sorted(
        [e for e in expenses if e.get('type') == 'expense'],
        key=lambda x: x.get('amount', 0), reverse=True)[:10]
    top_expenses_data = {
        'labels': [f"{e['category']} ({e['date']})" for e in top_expenses],
        'data': [e['amount'] for e in top_expenses]
    }
    # --- End New Cool Graphs Data ---
    # --- Donut Chart: Expense vs Income Proportion ---
    donut_data = {
        'labels': ['Expenses', 'Income'],
        'data': [total_expenses, total_income]
    }
    return render_template('index.html',
        expenses=expenses,
        categories=CATEGORIES,
        summary=summary,
        chart_data=chart_data,
        currencies=currencies,
        selected_currency=currency,
        budget_progress=budget_progress,
        user_groups=user_groups,
        selected_group=group_id,
        reminder_message=reminder_message,
        suggestions=suggestions,
        top_category=top_category,
        biggest_expense=biggest_expense,
        savings_rate=savings_rate,
        # New analysis data:
        months=months,
        monthly_expenses=monthly_expenses,
        monthly_income=monthly_income,
        monthly_savings_rate=monthly_savings_rate,
        top_cat_labels=top_cat_labels,
        top_cat_data=top_cat_data,
        biggest_expenses=biggest_expenses,
        stacked_bar_data=stacked_bar_data,
        top_expenses_data=top_expenses_data,
        donut_data=donut_data
    )

@main.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    user_id = session['user_id']
    user_groups = get_user_groups(user_id)
    if request.method == 'POST':
        # Prepare data for validation
        form_data = {
            'amount': request.form['amount'],
            'category': request.form['category'],
            'date': request.form['date'],
            'description': request.form['description'],
            'type': request.form.get('type', 'expense'),
            'currency': request.form.get('currency', 'INR'),
            'group_id': request.form.get('group_id') or None
        }
        
        # Validate the data
        validation_result = ExpenseValidator.validate_expense_data(form_data)
        
        if not validation_result.is_valid:
            # Show validation errors
            for error in validation_result.errors:
                flash(f'Error: {error}', 'error')
            return render_template('add_expense.html', 
                                categories=CATEGORIES, 
                                user_groups=user_groups,
                                form_data=form_data)
        
        # Show warnings if any
        for warning in validation_result.warnings:
            flash(f'Warning: {warning}', 'warning')
        
        # Add user_id to cleaned data
        data = validation_result.cleaned_data
        data['user_id'] = user_id
        
        # Add expense to database
        result = add_expense(data)
        if result:
            flash('Expense added successfully!', 'success')
        else:
            flash('Failed to add expense. Please try again.', 'error')
        
        return redirect(url_for('main.index'))
    
    return render_template('add_expense.html', categories=CATEGORIES, user_groups=user_groups)

@main.route('/edit/<expense_id>', methods=['GET', 'POST'])
@login_required
def edit(expense_id):
    expense = get_expense_by_id(expense_id)
    if not expense or expense.get('user_id') != session['user_id']:
        flash('Expense not found or access denied.', 'error')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # Prepare data for validation
        form_data = {
            'amount': request.form['amount'],
            'category': request.form['category'],
            'date': request.form['date'],
            'description': request.form['description'],
            'type': request.form.get('type', 'expense'),
            'currency': request.form.get('currency', 'INR')
        }
        
        # Validate the data
        validation_result = ExpenseValidator.validate_expense_data(form_data)
        
        if not validation_result.is_valid:
            # Show validation errors
            for error in validation_result.errors:
                flash(f'Error: {error}', 'error')
            return render_template('add_expense.html', 
                                expense=expense, 
                                categories=CATEGORIES, 
                                edit=True,
                                form_data=form_data)
        
        # Show warnings if any
        for warning in validation_result.warnings:
            flash(f'Warning: {warning}', 'warning')
        
        # Update expense in database
        result = update_expense(expense_id, validation_result.cleaned_data)
        if result:
            flash('Expense updated successfully!', 'success')
        else:
            flash('Failed to update expense. Please try again.', 'error')
        
        return redirect(url_for('main.index'))
    
    return render_template('add_expense.html', expense=expense, categories=CATEGORIES, edit=True)

@main.route('/delete/<expense_id>', methods=['POST'])
@login_required
def delete(expense_id):
    expense = get_expense_by_id(expense_id)
    if not expense or expense.get('user_id') != session['user_id']:
        flash('Expense not found or access denied.')
        return redirect(url_for('main.index'))
    delete_expense(expense_id)
    flash('Expense deleted!')
    return redirect(url_for('main.index'))

@main.route('/export/csv')
@login_required
def export_csv():
    user_id = session['user_id']
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    expenses = get_expenses(
        user_id=user_id,
        category=category if category else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None
    )
    filename = export_expenses_csv(expenses, user_id)
    return send_file(filename, as_attachment=True)

@main.route('/export/pdf')
@login_required
def export_pdf():
    user_id = session['user_id']
    category = request.args.get('category')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    expenses = get_expenses(
        user_id=user_id,
        category=category if category else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None
    )
    filename = export_expenses_pdf(expenses, user_id)
    return send_file(filename, as_attachment=True)

@main.route('/recurring', methods=['GET', 'POST'])
@login_required
def recurring():
    user_id = session['user_id']
    if request.method == 'POST':
        data = {
            'user_id': user_id,
            'amount': float(request.form['amount']),
            'category': request.form['category'],
            'description': request.form['description'],
            'type': request.form.get('type', 'expense'),
            'frequency': request.form['frequency'],
            'next_date': request.form['next_date'],
            'active': True
        }
        add_recurring_expense(data)
        flash('Recurring expense added!')
        return redirect(url_for('main.recurring'))
    recs = get_recurring_expenses(user_id)
    return render_template('recurring.html', recs=recs, categories=CATEGORIES)

@main.route('/recurring/deactivate/<rec_id>', methods=['POST'])
@login_required
def deactivate_recurring(rec_id):
    from bson.objectid import ObjectId
    mongo.db.recurring_expenses.update_one({'_id': ObjectId(rec_id)}, {'$set': {'active': False}})
    flash('Recurring expense deactivated!')
    return redirect(url_for('main.recurring'))

@main.route('/budgets', methods=['GET', 'POST'])
@login_required
def budgets():
    user_id = session['user_id']
    if request.method == 'POST':
        data = {
            'user_id': user_id,
            'category': request.form['category'],
            'amount': float(request.form['amount']),
            'period': request.form['period']
        }
        add_budget(data)
        flash('Budget added!')
        return redirect(url_for('main.budgets'))
    budgets = get_budgets(user_id)
    return render_template('budgets.html', budgets=budgets, categories=CATEGORIES)

@main.route('/budgets/delete/<budget_id>', methods=['POST'])
@login_required
def delete_budget_route(budget_id):
    delete_budget(budget_id)
    flash('Budget deleted!')
    return redirect(url_for('main.budgets'))

@main.route('/analytics')
@login_required
def analytics():
    user_id = session['user_id']
    expenses = get_expenses(user_id=user_id)
    from collections import defaultdict, Counter
    from datetime import datetime
    # Monthly totals
    monthly_totals = defaultdict(float)
    for e in expenses:
        if e.get('type') == 'expense':
            month = e.get('date', '')[:7]  # YYYY-MM
            monthly_totals[month] += e.get('amount', 0)
    months = sorted(monthly_totals.keys())
    month_data = [monthly_totals[m] for m in months]
    # Top categories
    cat_counter = Counter()
    for e in expenses:
        if e.get('type') == 'expense':
            cat_counter[e.get('category', 'Other')] += e.get('amount', 0)
    top_categories = cat_counter.most_common(5)
    # Trend: compare last two months
    trend = None
    if len(months) >= 2:
        last, prev = month_data[-1], month_data[-2]
        if last > prev:
            trend = 'up'
        elif last < prev:
            trend = 'down'
        else:
            trend = 'same'
    return render_template('analytics.html', months=months, month_data=month_data, top_categories=top_categories, trend=trend)

@main.route('/upload_receipt', methods=['GET', 'POST'])
@login_required
def upload_receipt():
    extracted = {}
    if request.method == 'POST':
        file = request.files['receipt']
        if file:
            filepath = os.path.join('static', 'uploads', file.filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            file.save(filepath)
            text = pytesseract.image_to_string(Image.open(filepath))
            # Simple parsing: look for amount, date, description
            import re
            amount_match = re.search(r'\b([0-9]+\.[0-9]{2})\b', text)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
            extracted['amount'] = amount_match.group(1) if amount_match else ''
            extracted['date'] = date_match.group(1) if date_match else ''
            extracted['description'] = text.split('\n')[0][:50] if text else ''
    return render_template('add_expense.html', categories=CATEGORIES, expense=extracted, ocr=True)

@main.route('/groups', methods=['GET', 'POST'])
@login_required
def groups():
    user_id = session['user_id']
    if request.method == 'POST':
        if 'group_name' in request.form:
            create_group(request.form['group_name'], user_id)
            flash('Group created!')
        elif 'join_group_id' in request.form:
            join_group(request.form['join_group_id'], user_id)
            flash('Joined group!')
        return redirect(url_for('main.groups'))
    user_groups = get_user_groups(user_id)
    return render_template('groups.html', user_groups=user_groups)

@main.route('/import', methods=['GET', 'POST'])
@login_required
def import_expenses():
    user_id = session['user_id']
    imported, errors = 0, 0
    if request.method == 'POST':
        file = request.files['file']
        if file:
            try:
                if file.filename.endswith('.csv'):
                    df = pd.read_csv(file)
                elif file.filename.endswith('.xls') or file.filename.endswith('.xlsx'):
                    df = pd.read_excel(file)
                else:
                    flash('Unsupported file type. Please upload CSV or Excel.')
                    return render_template('import.html', imported=imported, errors=errors)
                for _, row in df.iterrows():
                    try:
                        data = {
                            'user_id': user_id,
                            'amount': float(row['amount']),
                            'category': row.get('category', 'Other'),
                            'date': str(row['date']),
                            'description': row.get('description', ''),
                            'type': row.get('type', 'expense'),
                            'currency': row.get('currency', 'INR'),
                            'group_id': row.get('group_id') if 'group_id' in row else None
                        }
                        add_expense(data)
                        imported += 1
                    except Exception:
                        errors += 1
            except Exception:
                flash('Failed to process file. Please check the format.')
    return render_template('import.html', imported=imported, errors=errors)

@main.route('/reports', methods=['GET', 'POST'])
@login_required
def reports():
    user_id = session['user_id']
    categories = CATEGORIES
    user_groups = get_user_groups(user_id)
    filters = {
        'start_date': request.form.get('start_date', ''),
        'end_date': request.form.get('end_date', ''),
        'category': request.form.get('category', ''),
        'currency': request.form.get('currency', 'INR'),
        'group_id': request.form.get('group_id', '')
    }
    expenses = []
    if request.method == 'POST':
        expenses = get_expenses(
            user_id=user_id if not filters['group_id'] else None,
            category=filters['category'] or None,
            start_date=filters['start_date'] or None,
            end_date=filters['end_date'] or None
        )
        if filters['group_id']:
            expenses = [e for e in expenses if str(e.get('group_id')) == filters['group_id']]
        # Handle export
        if 'export' in request.form:
            if request.form['export'] == 'csv':
                filename = export_expenses_csv(expenses, user_id)
                return send_file(filename, as_attachment=True)
            elif request.form['export'] == 'pdf':
                filename = export_expenses_pdf(expenses, user_id)
                return send_file(filename, as_attachment=True)
    return render_template(
        'reports.html',
        categories=categories,
        user_groups=user_groups,
        filters=filters,
        expenses=expenses
    )

@main.route('/profile')
@login_required
def profile():
    user_id = session['user_id']
    user = find_user_by_username(session['username'])
    
    # Get user statistics
    expenses = get_expenses(user_id=user_id)
    stats = {
        'total_expenses': len(expenses),
        'categories_used': len(set(e.get('category') for e in expenses)),
        'days_active': len(set(e.get('date') for e in expenses)),
        'achievements': 0  # Placeholder for future achievements system
    }
    
    return render_template('profile.html', user=user, stats=stats)

@main.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    user_id = session['user_id']
    first_name = request.form.get('first_name', '')
    last_name = request.form.get('last_name', '')
    bio = request.form.get('bio', '')
    
    # Update user profile in database
    mongo = get_mongo()
    mongo.db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {
            'first_name': first_name,
            'last_name': last_name,
            'bio': bio
        }}
    )
    
    flash('Profile updated successfully!')
    return redirect(url_for('main.profile'))

@main.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    user_id = session['user_id']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Verify current password
    user = find_user_by_username(session['username'])
    if not verify_password(user['password'], current_password):
        flash('Current password is incorrect.')
        return redirect(url_for('main.profile'))
    
    # Check if new passwords match
    if new_password != confirm_password:
        flash('New passwords do not match.')
        return redirect(url_for('main.profile'))
    
    # Update password
    mongo = get_mongo()
    mongo.db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {'password': generate_password_hash(new_password)}}
    )
    
    flash('Password changed successfully!')
    return redirect(url_for('main.profile'))

@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user_id = session['user_id']
    
    # Get user settings from database
    mongo = get_mongo()
    user_settings = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    settings = user_settings.get('settings', {}) if user_settings else {}
    
    return render_template('settings.html', settings=settings)

@main.route('/settings/update', methods=['POST'])
@login_required
def update_settings():
    user_id = session['user_id']
    default_currency = request.form.get('default_currency', 'INR')
    date_format = request.form.get('date_format', 'YYYY-MM-DD')
    
    # Update settings in database
    mongo = get_mongo()
    mongo.db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {
            'settings.default_currency': default_currency,
            'settings.date_format': date_format
        }}
    )
    
    flash('Settings updated successfully!')
    return redirect(url_for('main.settings'))

@main.route('/settings/notifications', methods=['POST'])
@login_required
def update_notifications():
    user_id = session['user_id']
    email_notifications = 'email_notifications' in request.form
    browser_notifications = 'browser_notifications' in request.form
    budget_alerts = 'budget_alerts' in request.form
    weekly_reports = 'weekly_reports' in request.form
    
    # Update notification settings in database
    mongo = get_mongo()
    mongo.db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {
            'settings.email_notifications': email_notifications,
            'settings.browser_notifications': browser_notifications,
            'settings.budget_alerts': budget_alerts,
            'settings.weekly_reports': weekly_reports
        }}
    )
    
    flash('Notification settings updated successfully!')
    return redirect(url_for('main.settings'))

@main.route('/settings/delete-account', methods=['POST'])
@login_required
def delete_account():
    user_id = session['user_id']
    
    # Delete user data
    mongo = get_mongo()
    mongo.db.users.delete_one({'_id': ObjectId(user_id)})
    mongo.db.expenses.delete_many({'user_id': user_id})
    mongo.db.budgets.delete_many({'user_id': user_id})
    
    # Clear session
    session.clear()
    flash('Your account has been deleted successfully.')
    return redirect(url_for('auth.login'))

@main.route('/settings/reset', methods=['POST'])
@login_required
def reset_settings():
    user_id = session['user_id']
    
    # Reset settings to default
    mongo = get_mongo()
    mongo.db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$unset': {'settings': ''}}
    )
    
    flash('Settings have been reset to default values.')
    return redirect(url_for('main.settings'))

@main.route('/terms')
def terms():
    return render_template('terms.html')

@main.route('/privacy')
def privacy():
    return render_template('privacy.html')

@main.route('/submit-comment', methods=['POST'])
def submit_comment():
    """Handle comment submission from footer"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        comment = data.get('comment', '').strip()
        
        # Basic validation
        if not name or not comment:
            return jsonify({'success': False, 'message': 'Name and comment are required'})
        
        if len(name) > 100:
            return jsonify({'success': False, 'message': 'Name is too long'})
        
        if len(comment) > 1000:
            return jsonify({'success': False, 'message': 'Comment is too long'})
        
        # Add comment to database
        result = add_comment(name, comment)
        
        if result:
            return jsonify({'success': True, 'message': 'Comment submitted successfully! It will be reviewed before appearing.'})
        else:
            return jsonify({'success': False, 'message': 'Failed to submit comment. Please try again.'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': 'An error occurred. Please try again.'})

@main.route('/comments')
@login_required
def view_comments():
    """View all comments (admin only)"""
    comments = get_all_comments()
    return render_template('comments.html', comments=comments)

@main.route('/comments/approve/<comment_id>', methods=['POST'])
@login_required
def approve_comment_route(comment_id):
    """Approve a comment"""
    result = approve_comment(comment_id)
    if result:
        flash('Comment approved successfully!')
    else:
        flash('Failed to approve comment.')
    return redirect(url_for('main.view_comments'))

@main.route('/comments/delete/<comment_id>', methods=['POST'])
@login_required
def delete_comment_route(comment_id):
    """Delete a comment"""
    result = delete_comment(comment_id)
    if result:
        flash('Comment deleted successfully!')
    else:
        flash('Failed to delete comment.')
    return redirect(url_for('main.view_comments')) 