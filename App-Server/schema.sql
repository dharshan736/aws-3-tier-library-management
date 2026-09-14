CREATE TABLE IF NOT EXISTS users (
  user_id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(150) NOT NULL UNIQUE,
  phone VARCHAR(15),
  role ENUM('ADMIN', 'LIBRARIAN', 'BORROWER') NOT NULL DEFAULT 'BORROWER',
  password_hash VARCHAR(255) NOT NULL,
  status ENUM('ACTIVE', 'INACTIVE') NOT NULL DEFAULT 'ACTIVE',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS authors (
  author_id INT AUTO_INCREMENT PRIMARY KEY,
  author_name VARCHAR(150) NOT NULL
);
CREATE TABLE IF NOT EXISTS books (
  book_id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(200) NOT NULL,
  isbn VARCHAR(20) UNIQUE,
  author_id INT NOT NULL,
  category VARCHAR(100),
  publisher VARCHAR(150),
  publication_year YEAR,
  total_copies INT NOT NULL DEFAULT 1,
  available_copies INT NOT NULL DEFAULT 1,
  CONSTRAINT fk_books_author FOREIGN KEY (author_id) REFERENCES authors(author_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT chk_total_copies CHECK (total_copies >= 0),
  CONSTRAINT chk_available_copies CHECK (available_copies >= 0),
  CONSTRAINT chk_available_not_exceed_total CHECK (available_copies <= total_copies)
);
CREATE TABLE IF NOT EXISTS borrowings (
  borrowing_id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  book_id INT NOT NULL,
  issue_date DATE NOT NULL DEFAULT (CURRENT_DATE),
  due_date DATE NOT NULL,
  return_date DATE,
  status ENUM('BORROWED', 'RETURNED') NOT NULL DEFAULT 'BORROWED',
  CONSTRAINT fk_borrowings_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT fk_borrowings_book FOREIGN KEY (book_id) REFERENCES books(book_id) ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE INDEX idx_books_title ON books(title);
CREATE INDEX idx_books_author ON books(author_id);
CREATE INDEX idx_borrowings_user ON borrowings(user_id);
CREATE INDEX idx_borrowings_book ON borrowings(book_id);
CREATE INDEX idx_borrowings_status ON borrowings(status);
CREATE INDEX idx_borrowings_due_date ON borrowings(due_date);
