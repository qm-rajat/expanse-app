CATEGORIES = [
    'Food', 'Transportation', 'Utilities', 'Entertainment', 'Healthcare',
    'Education', 'Shopping', 'Travel', 'Others', 'Salary', 'Packet Money'
]

from flask import current_app
from bson.objectid import ObjectId
from flask_bcrypt import generate_password_hash, check_password_hash
import logging
from bson.errors import InvalidId
logger = logging.getLogger(__name__)

def get_mongo():
    """Get MongoDB instance from current app context"""
    from expense_tracker.app import mongo
    return mongo

def get_expenses(user_id=None, category=None, start_date=None, end_date=None):
    query = {}
    if user_id:
        query['user_id'] = user_id
    if category:
        query['category'] = category
    if start_date and end_date:
        query['date'] = {'$gte': start_date, '$lte': end_date}
    try:
        mongo = get_mongo()
        return list(mongo.db.expenses.find(query))
    except Exception as e:
        logger.error(f"Error getting expenses: {e}")
        return []

def add_expense(data):
    try:
        mongo = get_mongo()
        return mongo.db.expenses.insert_one(data)
    except Exception as e:
        logger.error(f"Error adding expense: {e}")
        return None

def update_expense(expense_id, data):
    try:
        oid = ObjectId(expense_id)
    except InvalidId:
        logger.error(f"Invalid expense_id: {expense_id}")
        return None
    try:
        mongo = get_mongo()
        return mongo.db.expenses.update_one({'_id': oid}, {'$set': data})
    except Exception as e:
        logger.error(f"Error updating expense: {e}")
        return None

def delete_expense(expense_id):
    try:
        oid = ObjectId(expense_id)
    except InvalidId:
        logger.error(f"Invalid expense_id: {expense_id}")
        return None
    try:
        mongo = get_mongo()
        return mongo.db.expenses.delete_one({'_id': oid})
    except Exception as e:
        logger.error(f"Error deleting expense: {e}")
        return None

def get_expense_by_id(expense_id):
    try:
        oid = ObjectId(expense_id)
    except InvalidId:
        logger.error(f"Invalid expense_id: {expense_id}")
        return None
    try:
        mongo = get_mongo()
        return mongo.db.expenses.find_one({'_id': oid})
    except Exception as e:
        logger.error(f"Error getting expense by id: {e}")
        return None

def create_user(username, email, password):
    try:
        hashed_pw = generate_password_hash(password)
        user = {
            'username': username,
            'email': email,
            'password': hashed_pw
        }
        mongo = get_mongo()
        return mongo.db.users.insert_one(user)
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return None

def find_user_by_username(username):
    try:
        mongo = get_mongo()
        return mongo.db.users.find_one({'username': username})
    except Exception as e:
        logger.error(f"Error finding user by username: {e}")
        return None

def find_user_by_email(email):
    try:
        mongo = get_mongo()
        return mongo.db.users.find_one({'email': email})
    except Exception as e:
        logger.error(f"Error finding user by email: {e}")
        return None

def verify_password(stored_password, provided_password):
    try:
        return check_password_hash(stored_password, provided_password)
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False

def add_recurring_expense(data):
    try:
        mongo = get_mongo()
        return mongo.db.recurring_expenses.insert_one(data)
    except Exception as e:
        logger.error(f"Error adding recurring expense: {e}")
        return None

def get_recurring_expenses(user_id):
    try:
        mongo = get_mongo()
        return list(mongo.db.recurring_expenses.find({'user_id': user_id, 'active': True}))
    except Exception as e:
        logger.error(f"Error getting recurring expenses: {e}")
        return []

def process_recurring_expenses(user_id):
    from datetime import datetime, timedelta
    recs = get_recurring_expenses(user_id)
    today = datetime.now().date().isoformat()
    for rec in recs:
        if rec['next_date'] <= today:
            # Add expense
            expense_data = {
                'user_id': user_id,
                'amount': rec['amount'],
                'category': rec['category'],
                'date': rec['next_date'],
                'description': rec['description'] + ' (Recurring)',
                'type': rec['type']
            }
            try:
                mongo = get_mongo()
                mongo.db.expenses.insert_one(expense_data)
            except Exception as e:
                logger.error(f"Error inserting recurring expense: {e}")
            # Update next_date
            freq = rec['frequency']
            next_date = datetime.fromisoformat(rec['next_date'])
            if freq == 'daily':
                next_date += timedelta(days=1)
            elif freq == 'weekly':
                next_date += timedelta(weeks=1)
            elif freq == 'monthly':
                next_date = (next_date.replace(day=1) + timedelta(days=32)).replace(day=1)
            try:
                mongo = get_mongo()
                mongo.db.recurring_expenses.update_one({'_id': rec['_id']}, {'$set': {'next_date': next_date.date().isoformat()}})
            except Exception as e:
                logger.error(f"Error updating recurring expense next_date: {e}")

def add_budget(data):
    try:
        mongo = get_mongo()
        return mongo.db.budgets.insert_one(data)
    except Exception as e:
        logger.error(f"Error adding budget: {e}")
        return None

def get_budgets(user_id):
    try:
        mongo = get_mongo()
        return list(mongo.db.budgets.find({'user_id': user_id}))
    except Exception as e:
        logger.error(f"Error getting budgets: {e}")
        return []

def update_budget(budget_id, data):
    try:
        oid = ObjectId(budget_id)
    except InvalidId:
        logger.error(f"Invalid budget_id: {budget_id}")
        return None
    try:
        mongo = get_mongo()
        return mongo.db.budgets.update_one({'_id': oid}, {'$set': data})
    except Exception as e:
        logger.error(f"Error updating budget: {e}")
        return None

def delete_budget(budget_id):
    try:
        oid = ObjectId(budget_id)
    except InvalidId:
        logger.error(f"Invalid budget_id: {budget_id}")
        return None
    try:
        mongo = get_mongo()
        return mongo.db.budgets.delete_one({'_id': oid})
    except Exception as e:
        logger.error(f"Error deleting budget: {e}")
        return None

def get_budget_for_category(user_id, category, period):
    try:
        mongo = get_mongo()
        return mongo.db.budgets.find_one({'user_id': user_id, 'category': category, 'period': period})
    except Exception as e:
        logger.error(f"Error getting budget for category: {e}")
        return None

def create_group(name, user_id):
    try:
        group = {'name': name, 'members': [user_id]}
        mongo = get_mongo()
        return mongo.db.groups.insert_one(group)
    except Exception as e:
        logger.error(f"Error creating group: {e}")
        return None

def join_group(group_id, user_id):
    try:
        oid = ObjectId(group_id)
    except InvalidId:
        logger.error(f"Invalid group_id: {group_id}")
        return None
    try:
        mongo = get_mongo()
        return mongo.db.groups.update_one({'_id': oid}, {'$addToSet': {'members': user_id}})
    except Exception as e:
        logger.error(f"Error joining group: {e}")
        return None

def get_user_groups(user_id):
    try:
        mongo = get_mongo()
        return list(mongo.db.groups.find({'members': user_id}))
    except Exception as e:
        logger.error(f"Error getting user groups: {e}")
        return []

def get_group_by_id(group_id):
    try:
        oid = ObjectId(group_id)
    except InvalidId:
        logger.error(f"Invalid group_id: {group_id}")
        return None
    try:
        mongo = get_mongo()
        return mongo.db.groups.find_one({'_id': oid})
    except Exception as e:
        logger.error(f"Error getting group by id: {e}")
        return None

def add_comment(name, comment):
    """Add a new comment to the database"""
    try:
        from datetime import datetime
        comment_data = {
            'name': name,
            'comment': comment,
            'timestamp': datetime.now(),
            'approved': False  # Comments need approval before showing
        }
        mongo = get_mongo()
        return mongo.db.comments.insert_one(comment_data)
    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        return None

def get_approved_comments(limit=10):
    """Get approved comments for display"""
    try:
        mongo = get_mongo()
        return list(mongo.db.comments.find({'approved': True}).sort('timestamp', -1).limit(limit))
    except Exception as e:
        logger.error(f"Error getting comments: {e}")
        return []

def get_all_comments(limit=50):
    """Get all comments for admin review"""
    try:
        mongo = get_mongo()
        return list(mongo.db.comments.find().sort('timestamp', -1).limit(limit))
    except Exception as e:
        logger.error(f"Error getting all comments: {e}")
        return []

def approve_comment(comment_id):
    """Approve a comment for display"""
    try:
        oid = ObjectId(comment_id)
    except InvalidId:
        logger.error(f"Invalid comment_id: {comment_id}")
        return None
    try:
        mongo = get_mongo()
        return mongo.db.comments.update_one({'_id': oid}, {'$set': {'approved': True}})
    except Exception as e:
        logger.error(f"Error approving comment: {e}")
        return None

def delete_comment(comment_id):
    """Delete a comment"""
    try:
        oid = ObjectId(comment_id)
    except InvalidId:
        logger.error(f"Invalid comment_id: {comment_id}")
        return None
    try:
        mongo = get_mongo()
        return mongo.db.comments.delete_one({'_id': oid})
    except Exception as e:
        logger.error(f"Error deleting comment: {e}")
        return None
