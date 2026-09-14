import os
from datetime import date, timedelta
from functools import wraps
from urllib.parse import quote_plus

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, Enum, func, or_
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash


load_dotenv()
db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-only-change-me')
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    app.config['SESSION_COOKIE_SECURE'] = os.getenv('SESSION_COOKIE_SECURE', '0') == '1'
    db_host = os.getenv('DB_HOST')
    if db_host:
        if db_host.startswith('arn:aws:rds:'):
            raise RuntimeError('DB_HOST must be the RDS endpoint DNS name, not the RDS ARN. Copy the Endpoint from RDS Connectivity & security.')
        db_port = os.getenv('DB_PORT', '3306')
        db_name = os.getenv('DB_NAME', 'library_management')
        db_user = quote_plus(os.getenv('DB_USER', ''))
        db_password = quote_plus(os.getenv('DB_PASSWORD', ''))
        database_url = f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    else:
        database_url = os.getenv('DATABASE_URL', 'sqlite:///library.db')
    if database_url.startswith('mysql://'):
        database_url = database_url.replace('mysql://', 'mysql+pymysql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    @app.after_request
    def allow_web_server_requests(response):
        allowed_origin = os.getenv('WEB_ORIGIN')
        if allowed_origin:
            response.headers['Access-Control-Allow-Origin'] = allowed_origin
            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
        return response

    @app.context_processor
    def inject_user():
        return {'current_user': session.get('user')}

    def role_required(*roles):
        def decorator(view):
            @wraps(view)
            def wrapped(*args, **kwargs):
                user = session.get('user')
                if not user:
                    return jsonify({'error': 'Authentication required'}), 401
                if user['role'] not in roles:
                    return jsonify({'error': 'You do not have permission for this action'}), 403
                return view(*args, **kwargs)
            return wrapped
        return decorator

    @app.get('/')
    def index():
        if session.get('user'):
            return redirect(url_for('portal', role=session['user']['role']))
        return render_template('login.html')

    @app.get('/portal/<role>')
    def portal(role):
        user = session.get('user')
        if not user or user['role'].lower() != role.lower():
            return redirect(url_for('index'))
        return render_template(f'{role}.html')

    @app.post('/api/login')
    def login():
        payload = request.get_json() or {}
        email = payload.get('email', '').strip().lower()
        password = payload.get('password', '')
        role = payload.get('role', '').upper()
        user = User.query.filter_by(email=email, role=role, status='ACTIVE').first()
        if not user or not check_password_hash(user.password_hash, password):
            return jsonify({'error': 'Invalid role, email, or password'}), 401
        session['user'] = {'id': user.user_id, 'name': user.name, 'email': user.email, 'role': user.role}
        return jsonify({'user': session['user'], 'redirect': f'/{user.role.lower()}.html'})

    @app.post('/api/logout')
    def logout():
        session.clear()
        return jsonify({'redirect': url_for('index')})

    @app.get('/api/me')
    def me():
        return jsonify({'user': session.get('user')})

    @app.get('/api/books')
    @role_required('ADMIN', 'LIBRARIAN', 'BORROWER')
    def books():
        search = request.args.get('search', '').strip()
        query = Book.query.join(Author)
        if search:
            query = query.filter(or_(Book.title.ilike(f'%{search}%'), Author.author_name.ilike(f'%{search}%')))
        return jsonify([book.to_dict() for book in query.order_by(Book.title).all()])

    @app.post('/api/books')
    @role_required('ADMIN', 'LIBRARIAN')
    def create_book():
        payload = request.get_json() or {}
        required = ['title', 'author_id', 'total_copies']
        if any(payload.get(field) in (None, '') for field in required):
            return jsonify({'error': 'Title, author, and total copies are required'}), 400
        total = int(payload['total_copies'])
        if total < 1:
            return jsonify({'error': 'Total copies must be at least 1'}), 400
        book = Book(title=payload['title'].strip(), isbn=payload.get('isbn') or None,
                    author_id=int(payload['author_id']), category=payload.get('category'),
                    publisher=payload.get('publisher'), publication_year=payload.get('publication_year'),
                    total_copies=total, available_copies=total)
        db.session.add(book)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'error': 'ISBN must be unique and the author must exist'}), 400
        return jsonify(book.to_dict()), 201

    @app.put('/api/books/<int:book_id>')
    @role_required('ADMIN', 'LIBRARIAN')
    def update_book(book_id):
        book = db.get_or_404(Book, book_id)
        payload = request.get_json() or {}
        for field in ('title', 'isbn', 'category', 'publisher', 'publication_year'):
            if field in payload:
                setattr(book, field, payload[field] or None)
        if 'total_copies' in payload:
            new_total = int(payload['total_copies'])
            borrowed = book.total_copies - book.available_copies
            if new_total < borrowed:
                return jsonify({'error': 'Total copies cannot be less than currently borrowed copies'}), 400
            book.total_copies = new_total
            book.available_copies = new_total - borrowed
        db.session.commit()
        return jsonify(book.to_dict())

    @app.get('/api/authors')
    @role_required('ADMIN', 'LIBRARIAN')
    def authors():
        return jsonify([author.to_dict() for author in Author.query.order_by(Author.author_name).all()])

    @app.post('/api/authors')
    @role_required('ADMIN', 'LIBRARIAN')
    def create_author():
        payload = request.get_json() or {}
        name = payload.get('author_name', '').strip()
        if not name:
            return jsonify({'error': 'Author name is required'}), 400
        author = Author(author_name=name)
        db.session.add(author)
        db.session.commit()
        return jsonify(author.to_dict()), 201

    @app.get('/api/users')
    @role_required('ADMIN')
    def users():
        return jsonify([user.to_dict() for user in User.query.order_by(User.created_at.desc()).all()])

    @app.post('/api/users')
    @role_required('ADMIN')
    def create_user():
        payload = request.get_json() or {}
        name, email, password, role = (payload.get(key, '').strip() for key in ('name', 'email', 'password', 'role'))
        role = role.upper()
        if not all((name, email, password)) or role not in ('ADMIN', 'LIBRARIAN', 'BORROWER'):
            return jsonify({'error': 'Name, email, password, and a valid role are required'}), 400
        user = User(name=name, email=email.lower(), phone=payload.get('phone'), role=role,
                    password_hash=generate_password_hash(password), status='ACTIVE')
        db.session.add(user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'error': 'Email is already registered'}), 400
        return jsonify(user.to_dict()), 201

    @app.get('/api/borrowings')
    @role_required('ADMIN', 'LIBRARIAN', 'BORROWER')
    def borrowings():
        query = Borrowing.query.join(User).join(Book)
        if session['user']['role'] == 'BORROWER':
            query = query.filter(Borrowing.user_id == session['user']['id'])
        return jsonify([item.to_dict() for item in query.order_by(Borrowing.issue_date.desc()).all()])

    @app.post('/api/borrow')
    @role_required('ADMIN', 'LIBRARIAN', 'BORROWER')
    def borrow_book():
        payload = request.get_json() or {}
        book = db.get_or_404(Book, int(payload.get('book_id', 0)))
        borrower_id = session['user']['id'] if session['user']['role'] == 'BORROWER' else int(payload.get('user_id', 0))
        user = db.session.get(User, borrower_id)
        if not user or user.status != 'ACTIVE':
            return jsonify({'error': 'Choose an active borrower'}), 400
        if book.available_copies < 1:
            return jsonify({'error': 'No copies are currently available'}), 409
        borrowing = Borrowing(user_id=user.user_id, book_id=book.book_id,
                              due_date=date.today() + timedelta(days=14), status='BORROWED')
        book.available_copies -= 1
        db.session.add(borrowing)
        db.session.commit()
        return jsonify(borrowing.to_dict()), 201

    @app.post('/api/return/<int:borrowing_id>')
    @role_required('ADMIN', 'LIBRARIAN')
    def return_book(borrowing_id):
        borrowing = db.get_or_404(Borrowing, borrowing_id)
        if borrowing.status == 'RETURNED':
            return jsonify({'error': 'This borrowing is already returned'}), 409
        borrowing.status = 'RETURNED'
        borrowing.return_date = date.today()
        borrowing.book.available_copies = min(borrowing.book.available_copies + 1, borrowing.book.total_copies)
        db.session.commit()
        return jsonify(borrowing.to_dict())

    @app.get('/api/dashboard')
    @role_required('ADMIN', 'LIBRARIAN', 'BORROWER')
    def dashboard():
        return jsonify({
            'total_titles': Book.query.count(),
            'total_copies': db.session.query(func.coalesce(func.sum(Book.total_copies), 0)).scalar(),
            'available_copies': db.session.query(func.coalesce(func.sum(Book.available_copies), 0)).scalar(),
            'active_users': User.query.filter_by(status='ACTIVE').count(),
            'active_borrowings': Borrowing.query.filter_by(status='BORROWED').count(),
        })

    with app.app_context():
        db.create_all()
        seed_demo_data()
    return app


class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True)
    phone = db.Column(db.String(15))
    role = db.Column(Enum('ADMIN', 'LIBRARIAN', 'BORROWER', name='user_roles'), nullable=False, default='BORROWER')
    password_hash = db.Column(db.String(255), nullable=False)
    status = db.Column(Enum('ACTIVE', 'INACTIVE', name='user_status'), nullable=False, default='ACTIVE')
    created_at = db.Column(db.DateTime, server_default=func.now())
    borrowings = db.relationship('Borrowing', back_populates='user')

    def to_dict(self):
        return {'user_id': self.user_id, 'name': self.name, 'email': self.email, 'phone': self.phone,
                'role': self.role, 'status': self.status, 'created_at': self.created_at.isoformat() if self.created_at else None}


class Author(db.Model):
    __tablename__ = 'authors'
    author_id = db.Column(db.Integer, primary_key=True)
    author_name = db.Column(db.String(150), nullable=False)
    books = db.relationship('Book', back_populates='author')

    def to_dict(self):
        return {'author_id': self.author_id, 'author_name': self.author_name}


class Book(db.Model):
    __tablename__ = 'books'
    book_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    isbn = db.Column(db.String(20), unique=True)
    author_id = db.Column(db.Integer, db.ForeignKey('authors.author_id'), nullable=False)
    category = db.Column(db.String(100))
    publisher = db.Column(db.String(150))
    publication_year = db.Column(db.Integer)
    total_copies = db.Column(db.Integer, nullable=False, default=1)
    available_copies = db.Column(db.Integer, nullable=False, default=1)
    __table_args__ = (CheckConstraint('total_copies >= 0'), CheckConstraint('available_copies >= 0'), CheckConstraint('available_copies <= total_copies'))
    author = db.relationship('Author', back_populates='books')
    borrowings = db.relationship('Borrowing', back_populates='book')

    def to_dict(self):
        return {'book_id': self.book_id, 'title': self.title, 'isbn': self.isbn, 'author_id': self.author_id,
                'author_name': self.author.author_name, 'category': self.category, 'publisher': self.publisher,
                'publication_year': self.publication_year, 'total_copies': self.total_copies,
                'available_copies': self.available_copies}


class Borrowing(db.Model):
    __tablename__ = 'borrowings'
    borrowing_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('books.book_id'), nullable=False)
    issue_date = db.Column(db.Date, nullable=False, default=date.today)
    due_date = db.Column(db.Date, nullable=False)
    return_date = db.Column(db.Date)
    status = db.Column(Enum('BORROWED', 'RETURNED', name='borrowing_status'), nullable=False, default='BORROWED')
    user = db.relationship('User', back_populates='borrowings')
    book = db.relationship('Book', back_populates='borrowings')

    def to_dict(self):
        return {'borrowing_id': self.borrowing_id, 'user_id': self.user_id, 'borrower_name': self.user.name,
                'book_id': self.book_id, 'title': self.book.title, 'issue_date': self.issue_date.isoformat(),
                'due_date': self.due_date.isoformat(), 'return_date': self.return_date.isoformat() if self.return_date else None,
                'status': self.status}


def seed_demo_data():
    if Author.query.count() == 0:
        authors = [Author(author_name=name) for name in ('Robert C. Martin', 'James Clear', 'Martin Fowler', 'Joshua Bloch', 'Andrew Hunt')]
        db.session.add_all(authors)
        db.session.flush()
        db.session.add_all([
            Book(title='Clean Code', isbn='9780132350884', author=authors[0], category='Programming', publisher='Prentice Hall', publication_year=2008, total_copies=5, available_copies=5),
            Book(title='Atomic Habits', isbn='9780735211292', author=authors[1], category='Self Help', publisher='Avery', publication_year=2018, total_copies=4, available_copies=4),
            Book(title='Refactoring', isbn='9780134757599', author=authors[2], category='Programming', publisher='Addison-Wesley', publication_year=2018, total_copies=3, available_copies=3),
        ])
    demo_users = [
        ('Library Admin', 'admin@library.local', 'ADMIN', 'admin123', '9876543210'),
        ('Maya Librarian', 'librarian@library.local', 'LIBRARIAN', 'librarian123', '9876543211'),
        ('Dharshan Member', 'borrower@library.local', 'BORROWER', 'borrower123', '9876543212'),
    ]
    for name, email, role, password, phone in demo_users:
        if not User.query.filter_by(email=email).first():
            db.session.add(User(name=name, email=email, role=role, password_hash=generate_password_hash(password), phone=phone))
    db.session.commit()


app = create_app()

if __name__ == '__main__':
    app.run(
        host=os.getenv('HOST', '0.0.0.0'),
        port=int(os.getenv('PORT', '5000')),
        debug=os.getenv('FLASK_DEBUG', '0') == '1',
    )
