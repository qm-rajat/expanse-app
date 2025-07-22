# 💸 Expense Tracker Web App

A modern, secure, and mobile-friendly expense tracker built with **Flask**, **MongoDB**, and **Progressive Web App (PWA)** technologies. Track your expenses and income, analyze your spending, and stay in control of your finances—anytime, anywhere!

---

## ✨ Features
- **Add, Edit, Delete Expenses & Income**
- **Custom Categories** (Food, Travel, Salary, Packet Money, and more)
- **Budgets & Alerts**: Set monthly budgets and get notified when you're close to the limit
- **Analytics & Charts**: Visualize your spending by category, time, and trends
- **Multi-Currency Support**: Track expenses in INR, USD, EUR, and more
- **Receipt OCR**: Scan and auto-fill expenses from receipts
- **Recurring Expenses**: Automate regular bills and subscriptions
- **Groups & Shared Expenses**: Manage group spending and settlements
- **Data Import/Export**: CSV, Excel, PDF
- **2FA (Two-Factor Authentication)**: Secure your account with email verification
- **PWA & Offline Support**: Install on your device and use offline
- **Mobile Widgets & Quick Add**: Fast entry from your home screen
- **Admin Dashboard**: User management, analytics, and settings

---

## 🏗️ How It Works
- **User Registration & Login**: Secure sign-up with email verification and optional 2FA
- **Expense/Income Management**: Add, edit, and categorize transactions
- **Budgets**: Set and monitor budgets per category
- **Analytics**: Get insights into your spending habits
- **Groups**: Create or join groups for shared expenses
- **Import/Export**: Move your data in and out easily

---

## 🔒 Security
- **2FA (Two-Factor Authentication)**: Email-based verification for logins
- **IDOR Protection**: Strict checks to ensure users can only access their own data
- **Security Headers**: HTTP headers to prevent XSS, clickjacking, and more
- **HTTPS by Default**: All traffic is encrypted (Vercel auto-enables HTTPS)
- **Session Security**: Secure, HTTP-only cookies
- **Input Validation**: All user input is validated and sanitized

---

## 🗄️ Database
- **MongoDB**: Flexible, scalable NoSQL database
- **Collections**:
  - `users`: User accounts and credentials
  - `expenses`: Expense and income records
  - `budgets`: User budgets per category
  - `groups`: Group info and memberships
  - `recurring_expenses`: Automated recurring transactions
- **Indexes**: Optimized for fast queries by user, date, and category

---

## 🛠️ Local Development
1. **Clone the repo & install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Create a `.env` file:**
   ```env
   SECRET_KEY=your-secret
   MONGO_URI=your-mongodb-uri
   # Email config for 2FA
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_SSL=True
   MAIL_USE_TLS=False
   MAIL_USERNAME=your-gmail@gmail.com
   MAIL_PASSWORD=your-app-password
   MAIL_DEFAULT_SENDER=expense.tracker.webapp0@gmail.com
   ```
3. **Run locally:**
   ```bash
   python run.py
   ```

---

## 🚀 Deploying to Vercel
1. Ensure your Flask entry point is at `api/index.py` (see this repo)
2. Add `vercel.json` for Vercel configuration
3. Push to GitHub and import the repo in [Vercel](https://expense-tracker-web-ten.vercel.app/register)
4. Set environment variables in the Vercel dashboard (see `.env` above)
5. Deploy! HTTPS is automatic 🎉

---

## 🌐 PWA & Mobile Experience
- **Installable**: Add to your Android/iOS home screen
- **Offline Support**: Works even without internet
- **Push Notifications**: Get alerts for budgets, reminders, and more
- **Responsive Design**: Looks great on all devices

---

## 🧩 Architecture
- **Backend**: Flask (Python), MongoDB, Flask-Mail, Flask-Bcrypt
- **Frontend**: Jinja2 templates, HTML5, CSS3, JavaScript
- **PWA**: Service Worker, manifest, offline.html
- **Deployment**: Vercel (serverless, HTTPS by default)

---

## 🧑‍💻 Contributing
Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change.

---

## 📸 Screenshots
<!-- Add screenshots/gifs here -->

---

## 📖 License
MIT 