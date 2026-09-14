"""Insert safe demo data into the configured database.

Run from the project folder:
    python seed_data.py

The database connection is read from .env through app.py.
"""

from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from app import app, db, User, Author, Book, Borrowing


DEMO_USERS = [
    {
        "name": "Library Admin",
        "email": "admin@library.local",
        "role": "ADMIN",
        "password": "admin123",
        "phone": "9876543210",
    },
    {
        "name": "Maya Librarian",
        "email": "librarian@library.local",
        "role": "LIBRARIAN",
        "password": "librarian123",
        "phone": "9876543211",
    },
    {
        "name": "Dharshan Member",
        "email": "borrower@library.local",
        "role": "BORROWER",
        "password": "borrower123",
        "phone": "9876543212",
    },
]

DEMO_BOOKS = [
    {
        "title": "Clean Code",
        "isbn": "9780132350884",
        "author_name": "Robert C. Martin",
        "category": "Programming",
        "publisher": "Prentice Hall",
        "publication_year": 2008,
        "total_copies": 5,
    },
    {
        "title": "Atomic Habits",
        "isbn": "9780735211292",
        "author_name": "James Clear",
        "category": "Self Help",
        "publisher": "Avery",
        "publication_year": 2018,
        "total_copies": 4,
    },
    {
        "title": "Refactoring",
        "isbn": "9780134757599",
        "author_name": "Martin Fowler",
        "category": "Programming",
        "publisher": "Addison-Wesley",
        "publication_year": 2018,
        "total_copies": 3,
    },
    {
        "title": "Effective Java",
        "isbn": "9780134685991",
        "author_name": "Joshua Bloch",
        "category": "Programming",
        "publisher": "Addison-Wesley",
        "publication_year": 2018,
        "total_copies": 4,
    },
    {
        "title": "The Pragmatic Programmer",
        "isbn": "9780135957059",
        "author_name": "Andrew Hunt",
        "category": "Programming",
        "publisher": "Addison-Wesley",
        "publication_year": 2019,
        "total_copies": 2,
    },
]


def create_demo_users():
    created = 0
    for item in DEMO_USERS:
        user = User.query.filter_by(email=item["email"]).first()
        if user:
            continue
        db.session.add(
            User(
                name=item["name"],
                email=item["email"],
                role=item["role"],
                phone=item["phone"],
                password_hash=generate_password_hash(item["password"]),
                status="ACTIVE",
            )
        )
        created += 1
    return created


def create_demo_books():
    created = 0
    for item in DEMO_BOOKS:
        if Book.query.filter_by(isbn=item["isbn"]).first():
            continue
        author = Author.query.filter_by(author_name=item["author_name"]).first()
        if not author:
            author = Author(author_name=item["author_name"])
            db.session.add(author)
            db.session.flush()
        db.session.add(
            Book(
                title=item["title"],
                isbn=item["isbn"],
                author_id=author.author_id,
                category=item["category"],
                publisher=item["publisher"],
                publication_year=item["publication_year"],
                total_copies=item["total_copies"],
                available_copies=item["total_copies"],
            )
        )
        created += 1
    return created


def create_demo_borrowings():
    """Create three sample transactions only when the table is empty."""
    if Borrowing.query.count() > 0:
        return 0

    borrower = User.query.filter_by(email="borrower@library.local").first()
    librarian = User.query.filter_by(email="librarian@library.local").first()
    clean_code = Book.query.filter_by(isbn="9780132350884").first()
    atomic_habits = Book.query.filter_by(isbn="9780735211292").first()
    refactoring = Book.query.filter_by(isbn="9780134757599").first()

    if not all((borrower, librarian, clean_code, atomic_habits, refactoring)):
        return 0

    today = date.today()
    records = [
        Borrowing(
            user_id=borrower.user_id,
            book_id=clean_code.book_id,
            issue_date=today - timedelta(days=5),
            due_date=today + timedelta(days=9),
            status="BORROWED",
        ),
        Borrowing(
            user_id=librarian.user_id,
            book_id=atomic_habits.book_id,
            issue_date=today - timedelta(days=25),
            due_date=today - timedelta(days=11),
            return_date=today - timedelta(days=8),
            status="RETURNED",
        ),
        Borrowing(
            user_id=borrower.user_id,
            book_id=refactoring.book_id,
            issue_date=today - timedelta(days=2),
            due_date=today + timedelta(days=12),
            status="BORROWED",
        ),
    ]
    clean_code.available_copies -= 1
    refactoring.available_copies -= 1
    db.session.add_all(records)
    return len(records)


def seed_database():
    with app.app_context():
        db.create_all()
        users_created = create_demo_users()
        books_created = create_demo_books()
        borrowings_created = create_demo_borrowings()
        db.session.commit()
        print("Database seed completed.")
        print(f"Users created: {users_created}")
        print(f"Books created: {books_created}")
        print(f"Borrowings created: {borrowings_created}")
        print(f"Current totals: {User.query.count()} users, {Author.query.count()} authors, "
              f"{Book.query.count()} books, {Borrowing.query.count()} borrowings")


if __name__ == "__main__":
    seed_database()
