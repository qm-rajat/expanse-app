import requests
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from datetime import datetime
import csv
import json
from datetime import datetime, timedelta
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import time
from functools import wraps
from flask import session, redirect, url_for, flash

CURRENCY_API_URL = 'https://api.exchangerate-api.com/v4/latest/'

# Currency conversion rates (you can replace with real API)
CURRENCY_RATES = {
    'INR': 1.0,
    'USD': 0.012,
    'EUR': 0.011,
    'GBP': 0.0095,
    'JPY': 1.8,
    'CAD': 0.016,
    'AUD': 0.018
}

class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass

class ExpenseType(Enum):
    EXPENSE = "expense"
    INCOME = "income"

@dataclass
class ValidationResult:
    """Result of validation operation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    cleaned_data: Optional[Dict] = None

class ExpenseValidator:
    """Comprehensive expense data validator"""
    
    MAX_AMOUNT = 999999999.99
    MIN_AMOUNT = 0.01
    MAX_DESCRIPTION_LENGTH = 500
    VALID_CATEGORIES = [
        'Food', 'Transportation', 'Utilities', 'Entertainment', 
        'Healthcare', 'Education', 'Shopping', 'Travel', 'Others',
        'Salary', 'Packet Money'
    ]
    VALID_CURRENCIES = ['INR', 'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD']
    
    @classmethod
    def validate_expense_data(cls, data: Dict) -> ValidationResult:
        """Validate expense data comprehensively"""
        errors = []
        warnings = []
        cleaned_data = {}
        
        # Required fields validation
        required_fields = ['amount', 'category', 'date', 'description', 'type']
        for field in required_fields:
            if field not in data or not data[field]:
                errors.append(f"{field.replace('_', ' ').title()} is required")
        
        if errors:
            return ValidationResult(False, errors, warnings)
        
        # Amount validation
        amount_result = cls._validate_amount(data.get('amount'))
        if not amount_result['is_valid']:
            errors.extend(amount_result['errors'])
        else:
            cleaned_data['amount'] = amount_result['cleaned_value']
            if amount_result['warnings']:
                warnings.extend(amount_result['warnings'])
        
        # Category validation
        category_result = cls._validate_category(data.get('category'))
        if not category_result['is_valid']:
            errors.extend(category_result['errors'])
        else:
            cleaned_data['category'] = category_result['cleaned_value']
        
        # Date validation
        date_result = cls._validate_date(data.get('date'))
        if not date_result['is_valid']:
            errors.extend(date_result['errors'])
        else:
            cleaned_data['date'] = date_result['cleaned_value']
            if date_result['warnings']:
                warnings.extend(date_result['warnings'])
        
        # Description validation
        description_result = cls._validate_description(data.get('description'))
        if not description_result['is_valid']:
            errors.extend(description_result['errors'])
        else:
            cleaned_data['description'] = description_result['cleaned_value']
            if description_result['warnings']:
                warnings.extend(description_result['warnings'])
        
        # Type validation
        type_result = cls._validate_type(data.get('type'))
        if not type_result['is_valid']:
            errors.extend(type_result['errors'])
        else:
            cleaned_data['type'] = type_result['cleaned_value']
        
        # Currency validation (optional)
        if 'currency' in data:
            currency_result = cls._validate_currency(data.get('currency'))
            if not currency_result['is_valid']:
                errors.extend(currency_result['errors'])
            else:
                cleaned_data['currency'] = currency_result['cleaned_value']
        else:
            cleaned_data['currency'] = 'INR'  # Default currency
        
        # Group ID validation (optional)
        if 'group_id' in data and data['group_id']:
            group_result = cls._validate_group_id(data.get('group_id'))
            if not group_result['is_valid']:
                errors.extend(group_result['errors'])
            else:
                cleaned_data['group_id'] = group_result['cleaned_value']
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data=cleaned_data
        )
    
    @classmethod
    def _validate_amount(cls, amount) -> Dict:
        """Validate and clean amount field"""
        errors = []
        warnings = []
        cleaned_value = None
        
        try:
            # Convert to float and round to 2 decimal places
            amount_float = float(amount)
            cleaned_value = round(amount_float, 2)
            
            # Check range
            if cleaned_value < cls.MIN_AMOUNT:
                errors.append(f"Amount must be at least {cls.MIN_AMOUNT}")
            elif cleaned_value > cls.MAX_AMOUNT:
                errors.append(f"Amount cannot exceed {cls.MAX_AMOUNT}")
            
            # Check for suspicious values
            if cleaned_value > 1000000:
                warnings.append("Amount seems unusually high. Please verify.")
            elif cleaned_value < 0.01:
                warnings.append("Amount seems unusually low. Please verify.")
                
        except (ValueError, TypeError):
            errors.append("Amount must be a valid number")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }
    
    @classmethod
    def _validate_category(cls, category) -> Dict:
        """Validate and clean category field"""
        errors = []
        warnings = []
        cleaned_value = None
        
        if not category or not str(category).strip():
            errors.append("Category is required")
        else:
            cleaned_value = str(category).strip()
            if cleaned_value not in cls.VALID_CATEGORIES:
                errors.append(f"Category must be one of: {', '.join(cls.VALID_CATEGORIES)}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }
    
    @classmethod
    def _validate_date(cls, date) -> Dict:
        """Validate and clean date field"""
        errors = []
        warnings = []
        cleaned_value = None
        
        if not date:
            errors.append("Date is required")
        else:
            try:
                # Try to parse the date
                if isinstance(date, str):
                    # Handle different date formats
                    date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']
                    parsed_date = None
                    
                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.strptime(date, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if parsed_date is None:
                        errors.append("Date must be in YYYY-MM-DD format")
                    else:
                        cleaned_value = parsed_date.strftime('%Y-%m-%d')
                else:
                    # Assume it's already a datetime object
                    cleaned_value = date.strftime('%Y-%m-%d')
                
                # Check if date is in reasonable range
                if cleaned_value:
                    date_obj = datetime.strptime(cleaned_value, '%Y-%m-%d')
                    today = datetime.now()
                    
                    if date_obj > today + timedelta(days=30):
                        warnings.append("Date is more than 30 days in the future")
                    elif date_obj < today - timedelta(days=365*10):
                        warnings.append("Date is more than 10 years in the past")
                        
            except Exception as e:
                errors.append(f"Invalid date format: {str(e)}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }
    
    @classmethod
    def _validate_description(cls, description) -> Dict:
        """Validate and clean description field"""
        errors = []
        warnings = []
        cleaned_value = None
        
        if not description or not str(description).strip():
            errors.append("Description is required")
        else:
            cleaned_value = str(description).strip()
            
            # Check length
            if len(cleaned_value) > cls.MAX_DESCRIPTION_LENGTH:
                errors.append(f"Description cannot exceed {cls.MAX_DESCRIPTION_LENGTH} characters")
            
            # Check for suspicious content
            suspicious_patterns = [
                r'<script', r'javascript:', r'on\w+\s*=',  # XSS patterns
                r'http[s]?://',  # URLs
                r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',  # Credit card numbers
            ]
            
            for pattern in suspicious_patterns:
                if re.search(pattern, cleaned_value, re.IGNORECASE):
                    warnings.append("Description contains potentially sensitive information")
                    break
            
            # Check for very short descriptions
            if len(cleaned_value) < 3:
                warnings.append("Description seems too short. Please provide more details.")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }
    
    @classmethod
    def _validate_type(cls, expense_type) -> Dict:
        """Validate and clean type field"""
        errors = []
        warnings = []
        cleaned_value = None
        
        if not expense_type:
            cleaned_value = 'expense'  # Default value
        else:
            cleaned_value = str(expense_type).lower().strip()
            if cleaned_value not in ['expense', 'income']:
                errors.append("Type must be either 'expense' or 'income'")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }
    
    @classmethod
    def _validate_currency(cls, currency) -> Dict:
        """Validate and clean currency field"""
        errors = []
        warnings = []
        cleaned_value = None
        
        if not currency:
            cleaned_value = 'INR'  # Default currency
        else:
            cleaned_value = str(currency).upper().strip()
            if cleaned_value not in cls.VALID_CURRENCIES:
                errors.append(f"Currency must be one of: {', '.join(cls.VALID_CURRENCIES)}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }
    
    @classmethod
    def _validate_group_id(cls, group_id) -> Dict:
        """Validate and clean group_id field"""
        errors = []
        warnings = []
        cleaned_value = None
        
        if group_id:
            # Basic ObjectId validation (MongoDB)
            if not re.match(r'^[0-9a-fA-F]{24}$', str(group_id)):
                errors.append("Invalid group ID format")
            else:
                cleaned_value = str(group_id)
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }

class UserValidator:
    """User data validator"""
    
    MIN_USERNAME_LENGTH = 3
    MAX_USERNAME_LENGTH = 30
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    
    @classmethod
    def validate_user_data(cls, data: Dict) -> ValidationResult:
        """Validate user registration/login data"""
        errors = []
        warnings = []
        cleaned_data = {}
        
        # Username validation
        if 'username' in data:
            username_result = cls._validate_username(data.get('username'))
            if not username_result['is_valid']:
                errors.extend(username_result['errors'])
            else:
                cleaned_data['username'] = username_result['cleaned_value']
                if username_result['warnings']:
                    warnings.extend(username_result['warnings'])
        
        # Email validation
        if 'email' in data:
            email_result = cls._validate_email(data.get('email'))
            if not email_result['is_valid']:
                errors.extend(email_result['errors'])
            else:
                cleaned_data['email'] = email_result['cleaned_value']
        
        # Password validation
        if 'password' in data:
            password_result = cls._validate_password(data.get('password'))
            if not password_result['is_valid']:
                errors.extend(password_result['errors'])
            else:
                cleaned_data['password'] = password_result['cleaned_value']
                if password_result['warnings']:
                    warnings.extend(password_result['warnings'])
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            cleaned_data=cleaned_data
        )
    
    @classmethod
    def _validate_username(cls, username) -> Dict:
        """Validate username"""
        errors = []
        warnings = []
        cleaned_value = None
        
        if not username or not str(username).strip():
            errors.append("Username is required")
        else:
            cleaned_value = str(username).strip().lower()
            
            # Check length
            if len(cleaned_value) < cls.MIN_USERNAME_LENGTH:
                errors.append(f"Username must be at least {cls.MIN_USERNAME_LENGTH} characters")
            elif len(cleaned_value) > cls.MAX_USERNAME_LENGTH:
                errors.append(f"Username cannot exceed {cls.MAX_USERNAME_LENGTH} characters")
            
            # Check for valid characters
            if not re.match(r'^[a-zA-Z0-9_]+$', cleaned_value):
                errors.append("Username can only contain letters, numbers, and underscores")
            
            # Check for reserved words
            reserved_words = ['admin', 'root', 'system', 'user', 'test']
            if cleaned_value in reserved_words:
                warnings.append("Username contains a reserved word")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }
    
    @classmethod
    def _validate_email(cls, email) -> Dict:
        """Validate email address"""
        errors = []
        warnings = []
        cleaned_value = None
        
        if not email or not str(email).strip():
            errors.append("Email is required")
        else:
            cleaned_value = str(email).strip().lower()
            
            # Basic email validation
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, cleaned_value):
                errors.append("Invalid email format")
            
            # Check for disposable email domains
            disposable_domains = ['tempmail.com', '10minutemail.com', 'guerrillamail.com']
            domain = cleaned_value.split('@')[1] if '@' in cleaned_value else ''
            if domain in disposable_domains:
                warnings.append("Disposable email addresses are not recommended")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }
    
    @classmethod
    def _validate_password(cls, password) -> Dict:
        """Validate password strength"""
        errors = []
        warnings = []
        cleaned_value = None
        
        if not password:
            errors.append("Password is required")
        else:
            cleaned_value = str(password)
            
            # Check length
            if len(cleaned_value) < cls.MIN_PASSWORD_LENGTH:
                errors.append(f"Password must be at least {cls.MIN_PASSWORD_LENGTH} characters")
            elif len(cleaned_value) > cls.MAX_PASSWORD_LENGTH:
                errors.append(f"Password cannot exceed {cls.MAX_PASSWORD_LENGTH} characters")
            
            # Check complexity
            if not re.search(r'[A-Z]', cleaned_value):
                warnings.append("Password should contain at least one uppercase letter")
            if not re.search(r'[a-z]', cleaned_value):
                warnings.append("Password should contain at least one lowercase letter")
            if not re.search(r'\d', cleaned_value):
                warnings.append("Password should contain at least one number")
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', cleaned_value):
                warnings.append("Password should contain at least one special character")
            
            # Check for common passwords
            common_passwords = ['password', '123456', 'qwerty', 'admin']
            if cleaned_value.lower() in common_passwords:
                errors.append("Password is too common. Please choose a stronger password")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'cleaned_value': cleaned_value
        }

def convert_currency(amount, from_currency, to_currency):
    if from_currency == to_currency:
        return amount
    url = f'{CURRENCY_API_URL}{from_currency}'
    try:
        response = requests.get(url)
        data = response.json()
        rate = data['rates'].get(to_currency)
        if rate:
            return round(amount * rate, 2)
        else:
            return None
    except Exception:
        return None

def export_expenses_csv(expenses, user_id):
    df = pd.DataFrame(expenses)
    if '_id' in df.columns:
        df = df.drop(columns=['_id'])
    os.makedirs('exports', exist_ok=True)
    filename = f'exports/expenses_{user_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.csv'
    df.to_csv(filename, index=False)
    return filename

def export_expenses_pdf(expenses, user_id):
    os.makedirs('exports', exist_ok=True)
    filename = f'exports/expenses_{user_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}.pdf'
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    c.setFont('Helvetica', 12)
    y = height - 40
    c.drawString(30, y, 'Date')
    c.drawString(100, y, 'Category')
    c.drawString(200, y, 'Description')
    c.drawString(350, y, 'Type')
    c.drawString(420, y, 'Amount')
    y -= 20
    for exp in expenses:
        c.drawString(30, y, str(exp.get('date', '')))
        c.drawString(100, y, str(exp.get('category', '')))
        c.drawString(200, y, str(exp.get('description', '')))
        c.drawString(350, y, str(exp.get('type', '')))
        c.drawString(420, y, str(exp.get('amount', '')))
        y -= 20
        if y < 40:
            c.showPage()
            y = height - 40
    c.save()
    return filename

def check_session_expiry():
    """
    Check if the current session is still valid.
    Returns True if session is valid, False otherwise.
    """
    if 'user_id' not in session:
        return False
    
    # If it's a "Remember Me" session, check if it's within 30 days
    if session.get('remember_me'):
        login_time = session.get('login_time', 0)
        current_time = int(time.time())
        # 30 days in seconds
        max_session_duration = 30 * 24 * 60 * 60
        
        if current_time - login_time > max_session_duration:
            # Session expired, clear it
            session.clear()
            return False
    
    return True

def require_login(f):
    """
    Decorator to require login for routes.
    Checks session expiry and redirects to login if needed.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not check_session_expiry():
            flash('Your session has expired. Please log in again.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
