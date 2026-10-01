import csv
import io
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, Response, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expenses.db"
db = SQLAlchemy(app)
import os
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-key")
login_manager = LoginManager(app)
login_manager.login_view = "login"


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount_paise = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # e.g. 2026-09
    limit_paise = db.Column(db.Integer, nullable=False)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

with app.app_context():
    db.create_all()


CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Other"]


@app.route("/")
@login_required
def home():
    selected = request.args.get("category", "")
    month = request.args.get("month", "")  # format: 2026-09

    query = Expense.query.filter_by(user_id=current_user.id)
    if selected:
        query = query.filter_by(category=selected)
    if month:
        year, mon = month.split("-")
        query = query.filter(
            db.extract("year", Expense.date) == int(year),
            db.extract("month", Expense.date) == int(mon),
        )

    expenses = query.order_by(Expense.date.desc()).all()
    total = sum(e.amount_paise for e in expenses)

    breakdown = {}
    for e in expenses:
        breakdown[e.category] = breakdown.get(e.category, 0) + e.amount_paise

    monthly = {}
    all_expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date).all()
    for e in all_expenses:
        key = e.date.strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0) + e.amount_paise

    budget_month = month or date.today().strftime("%Y-%m")
    budget = Budget.query.filter_by(user_id=current_user.id, month=budget_month).first()
    budget_limit = budget.limit_paise if budget else None
    budget_spent = monthly.get(budget_month, 0)

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        categories=CATEGORIES,
        selected=selected,
        month=month,
        breakdown=breakdown,
        monthly=monthly,
        budget_month=budget_month,
        budget_limit=budget_limit,
        budget_spent=budget_spent,
    )

@app.route("/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        amount = float(request.form["amount"])
        expense = Expense(
            user_id=current_user.id,
            amount_paise=round(amount * 100),
            category=request.form["category"],
            date=datetime.strptime(request.form["date"], "%Y-%m-%d").date(),
            note=request.form["note"],
        )
        db.session.add(expense)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("add_expense.html")

@app.route("/delete/<int:expense_id>", methods=["POST"])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    db.session.delete(expense)
    db.session.commit()
    return redirect(url_for("home"))

@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.filter_by(id=expense_id, user_id=current_user.id).first_or_404()
    if request.method == "POST":
        expense.amount_paise = round(float(request.form["amount"]) * 100)
        expense.category = request.form["category"]
        expense.date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
        expense.note = request.form["note"]
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("edit_expense.html", expense=expense)

@app.route("/budget", methods=["POST"])
@login_required
def set_budget():
    month = request.form["month"]
    limit = round(float(request.form["limit"]) * 100)
    budget = Budget.query.filter_by(user_id=current_user.id, month=month).first()
    if budget:
        budget.limit_paise = limit
    else:
        db.session.add(Budget(user_id=current_user.id, month=month, limit_paise=limit))
    db.session.commit()
    return redirect(url_for("home", month=month))

@app.route("/export")
@login_required
def export_csv():
    expenses = Expense.query.filter_by(user_id=current_user.id).order_by(Expense.date.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Category", "Amount (Rs)", "Note"])
    for e in expenses:
        writer.writerow([e.date, e.category, f"{e.amount_paise / 100:.2f}", e.note or ""])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or len(password) < 6:
            flash("Username is required and password must be at least 6 characters.")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("That username is already taken.")
            return redirect(url_for("register"))

        user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for("home"))
    return render_template("register.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for("home"))

        flash("Wrong username or password.")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("login"))
if __name__ == "__main__":
    app.run(debug=True)