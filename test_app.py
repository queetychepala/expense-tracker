import pytest
from datetime import date

from app import app, db, User, Expense


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.engine.dispose()
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def register(client, username, password="secret123"):
    return client.post(
        "/register",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def test_home_requires_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_register_and_see_home(client):
    response = register(client, "alice")
    assert response.status_code == 200
    assert b"My Expenses" in response.data


def test_short_password_rejected(client):
    register(client, "bob", password="123")
    assert User.query.filter_by(username="bob").first() is None


def test_add_expense(client):
    register(client, "alice")
    client.post(
        "/add",
        data={
            "amount": "250",
            "category": "Food",
            "date": date.today().isoformat(),
            "note": "Lunch",
        },
    )
    expense = Expense.query.first()
    assert expense.amount_paise == 25000
    assert expense.category == "Food"


def test_users_cannot_see_each_others_expenses(client):
    register(client, "alice")
    client.post(
        "/add",
        data={
            "amount": "999",
            "category": "Travel",
            "date": date.today().isoformat(),
            "note": "SecretTrip",
        },
    )
    client.get("/logout")

    register(client, "bob")
    response = client.get("/")
    assert b"SecretTrip" not in response.data