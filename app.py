from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expenses.db"
db = SQLAlchemy(app)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount_paise = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(200))


with app.app_context():
    db.create_all()


CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Other"]


@app.route("/")
def home():
    selected = request.args.get("category", "")
    month = request.args.get("month", "")  # format: 2026-09

    query = Expense.query
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
    all_expenses = Expense.query.order_by(Expense.date).all()
    for e in all_expenses:
        key = e.date.strftime("%Y-%m")
        monthly[key] = monthly.get(key, 0) + e.amount_paise

    return render_template(
        "index.html",
        expenses=expenses,
        total=total,
        categories=CATEGORIES,
        selected=selected,
        month=month,
        breakdown=breakdown,
        monthly=monthly,
    )

@app.route("/add", methods=["GET", "POST"])
def add_expense():
    if request.method == "POST":
        amount = float(request.form["amount"])
        expense = Expense(
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
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    return redirect(url_for("home"))

@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if request.method == "POST":
        expense.amount_paise = round(float(request.form["amount"]) * 100)
        expense.category = request.form["category"]
        expense.date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
        expense.note = request.form["note"]
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("edit_expense.html", expense=expense)

if __name__ == "__main__":
    app.run(debug=True)