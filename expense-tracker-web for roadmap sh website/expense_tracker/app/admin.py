from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from .models import (
    get_all_comments, approve_comment, delete_comment, 
    find_user_by_username, get_expenses, get_budgets, get_recurring_expenses,
    add_comment, get_approved_comments
)
from .utils import check_session_expiry
from functools import wraps
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import json

admin = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_session_expiry():
            flash('Please log in to access this page.')
            return redirect(url_for('auth.login'))
        
        # Check if user is admin (you can modify this logic based on your admin system)
        # For now, we'll use a simple check - you can enhance this later
        if session.get('username') not in ['admin', 'superuser']:  # Add your admin usernames
            flash('Access denied. Admin privileges required.')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/admin')
@admin_required
def dashboard():
    """Admin Dashboard with system overview"""
    from expense_tracker.app import mongo
    
    # Get system statistics
    total_users = mongo.db.users.count_documents({})
    total_expenses = mongo.db.expenses.count_documents({})
    total_budgets = mongo.db.budgets.count_documents({})
    total_comments = mongo.db.comments.count_documents({})
    pending_comments = mongo.db.comments.count_documents({'approved': False})
    
    # Get recent activity
    recent_expenses = list(mongo.db.expenses.find().sort('_id', -1).limit(10))
    recent_users = list(mongo.db.users.find().sort('_id', -1).limit(5))
    
    # Get monthly statistics for charts
    current_month = datetime.now().strftime('%Y-%m')
    monthly_expenses = list(mongo.db.expenses.find({
        'date': {'$regex': f'^{current_month}'}
    }))
    
    # Calculate monthly totals
    monthly_total = sum(exp.get('amount', 0) for exp in monthly_expenses)
    monthly_count = len(monthly_expenses)
    
    # Get top categories
    categories = Counter(exp.get('category', 'Other') for exp in monthly_expenses)
    top_categories = categories.most_common(5)
    
    # Get user activity
    user_activity = list(mongo.db.expenses.aggregate([
        {'$group': {'_id': '$user_id', 'count': {'$sum': 1}, 'total': {'$sum': '$amount'}}},
        {'$sort': {'count': -1}},
        {'$limit': 10}
    ]))
    
    stats = {
        'total_users': total_users,
        'total_expenses': total_expenses,
        'total_budgets': total_budgets,
        'total_comments': total_comments,
        'pending_comments': pending_comments,
        'monthly_total': monthly_total,
        'monthly_count': monthly_count,
        'top_categories': top_categories,
        'user_activity': user_activity
    }
    
    return render_template('admin/dashboard.html', 
                         stats=stats, 
                         recent_expenses=recent_expenses,
                         recent_users=recent_users)

@admin.route('/admin/users')
@admin_required
def users():
    """User Management"""
    from expense_tracker.app import mongo
    
    # Get all users with their statistics
    users = list(mongo.db.users.find())
    
    # Add statistics for each user
    for user in users:
        user_id = str(user['_id'])
        user['expense_count'] = mongo.db.expenses.count_documents({'user_id': user_id})
        user['budget_count'] = mongo.db.budgets.count_documents({'user_id': user_id})
        user['total_spent'] = sum(exp.get('amount', 0) for exp in mongo.db.expenses.find({'user_id': user_id, 'type': 'expense'}))
        user['last_activity'] = mongo.db.expenses.find({'user_id': user_id}).sort('_id', -1).limit(1)
        last_expense = list(user['last_activity'])
        user['last_activity'] = last_expense[0] if last_expense else None
    
    return render_template('admin/users.html', users=users)

@admin.route('/admin/users/<user_id>')
@admin_required
def user_detail(user_id):
    """User Detail View"""
    from expense_tracker.app import mongo
    from bson.objectid import ObjectId
    
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
        if not user:
            flash('User not found.')
            return redirect(url_for('admin.users'))
        
        # Get user's expenses
        expenses = list(mongo.db.expenses.find({'user_id': user_id}).sort('_id', -1).limit(50))
        budgets = list(mongo.db.budgets.find({'user_id': user_id}))
        
        # Calculate statistics
        total_expenses = sum(exp.get('amount', 0) for exp in expenses if exp.get('type') == 'expense')
        total_income = sum(exp.get('amount', 0) for exp in expenses if exp.get('type') == 'income')
        
        # Get category breakdown
        categories = Counter(exp.get('category', 'Other') for exp in expenses if exp.get('type') == 'expense')
        
        user_stats = {
            'total_expenses': total_expenses,
            'total_income': total_income,
            'balance': total_income - total_expenses,
            'expense_count': len([e for e in expenses if e.get('type') == 'expense']),
            'income_count': len([e for e in expenses if e.get('type') == 'income']),
            'categories': dict(categories.most_common(10))
        }
        
        return render_template('admin/user_detail.html', 
                             user=user, 
                             expenses=expenses, 
                             budgets=budgets,
                             stats=user_stats)
    
    except Exception as e:
        flash('Error loading user details.')
        return redirect(url_for('admin.users'))

@admin.route('/admin/users/<user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete User"""
    from expense_tracker.app import mongo
    from bson.objectid import ObjectId
    
    try:
        # Delete user and all their data
        mongo.db.users.delete_one({'_id': ObjectId(user_id)})
        mongo.db.expenses.delete_many({'user_id': user_id})
        mongo.db.budgets.delete_many({'user_id': user_id})
        mongo.db.recurring_expenses.delete_many({'user_id': user_id})
        
        flash('User and all associated data deleted successfully.')
    except Exception as e:
        flash('Error deleting user.')
    
    return redirect(url_for('admin.users'))

@admin.route('/admin/comments')
@admin_required
def comments():
    """Comment Management"""
    comments = get_all_comments(limit=100)
    return render_template('admin/comments.html', comments=comments)

@admin.route('/admin/comments/approve/<comment_id>', methods=['POST'])
@admin_required
def approve_comment_admin(comment_id):
    """Approve Comment"""
    result = approve_comment(comment_id)
    if result:
        flash('Comment approved successfully!')
    else:
        flash('Failed to approve comment.')
    return redirect(url_for('admin.comments'))

@admin.route('/admin/comments/delete/<comment_id>', methods=['POST'])
@admin_required
def delete_comment_admin(comment_id):
    """Delete Comment"""
    result = delete_comment(comment_id)
    if result:
        flash('Comment deleted successfully!')
    else:
        flash('Failed to delete comment.')
    return redirect(url_for('admin.comments'))

@admin.route('/admin/comments/bulk-action', methods=['POST'])
@admin_required
def bulk_comment_action():
    """Bulk comment actions"""
    action = request.form.get('action')
    comment_ids = request.form.getlist('comment_ids')
    
    if not comment_ids:
        flash('No comments selected.')
        return redirect(url_for('admin.comments'))
    
    success_count = 0
    for comment_id in comment_ids:
        if action == 'approve':
            if approve_comment(comment_id):
                success_count += 1
        elif action == 'delete':
            if delete_comment(comment_id):
                success_count += 1
    
    flash(f'{success_count} comments {action}d successfully.')
    return redirect(url_for('admin.comments'))

@admin.route('/admin/analytics')
@admin_required
def analytics():
    """System Analytics"""
    from expense_tracker.app import mongo
    
    # Get date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Get expenses for the last 30 days
    expenses = list(mongo.db.expenses.find({
        'date': {
            '$gte': start_date.strftime('%Y-%m-%d'),
            '$lte': end_date.strftime('%Y-%m-%d')
        }
    }))
    
    # Daily expense trend
    daily_expenses = defaultdict(float)
    for exp in expenses:
        if exp.get('type') == 'expense':
            daily_expenses[exp.get('date', '')] += exp.get('amount', 0)
    
    # Category breakdown
    categories = Counter(exp.get('category', 'Other') for exp in expenses if exp.get('type') == 'expense')
    
    # User activity
    user_activity = list(mongo.db.expenses.aggregate([
        {'$match': {
            'date': {
                '$gte': start_date.strftime('%Y-%m-%d'),
                '$lte': end_date.strftime('%Y-%m-%d')
            }
        }},
        {'$group': {'_id': '$user_id', 'count': {'$sum': 1}, 'total': {'$sum': '$amount'}}},
        {'$sort': {'count': -1}},
        {'$limit': 10}
    ]))
    
    analytics_data = {
        'daily_expenses': dict(daily_expenses),
        'categories': dict(categories.most_common(10)),
        'user_activity': user_activity,
        'total_expenses': len(expenses),
        'total_amount': sum(exp.get('amount', 0) for exp in expenses if exp.get('type') == 'expense')
    }
    
    return render_template('admin/analytics.html', analytics=analytics_data)

@admin.route('/admin/settings')
@admin_required
def settings():
    """Admin Settings"""
    from expense_tracker.app import mongo
    
    # Get system settings
    settings = mongo.db.settings.find_one({'_id': 'system'}) or {}
    
    return render_template('admin/settings.html', settings=settings)

@admin.route('/admin/settings/update', methods=['POST'])
@admin_required
def update_settings():
    """Update System Settings"""
    from expense_tracker.app import mongo
    
    try:
        # Update system settings
        mongo.db.settings.update_one(
            {'_id': 'system'},
            {
                '$set': {
                    'maintenance_mode': 'maintenance_mode' in request.form,
                    'comment_approval_required': 'comment_approval_required' in request.form,
                    'max_file_size': int(request.form.get('max_file_size', 5)),
                    'session_timeout': int(request.form.get('session_timeout', 30))
                }
            },
            upsert=True
        )
        
        flash('System settings updated successfully!')
    except Exception as e:
        flash('Error updating settings.')
    
    return redirect(url_for('admin.settings'))

@admin.route('/admin/api/stats')
@admin_required
def api_stats():
    """API endpoint for dashboard statistics"""
    from expense_tracker.app import mongo
    
    # Get real-time statistics
    stats = {
        'total_users': mongo.db.users.count_documents({}),
        'total_expenses': mongo.db.expenses.count_documents({}),
        'pending_comments': mongo.db.comments.count_documents({'approved': False}),
        'today_expenses': mongo.db.expenses.count_documents({
            'date': datetime.now().strftime('%Y-%m-%d')
        })
    }
    
    return jsonify(stats) 