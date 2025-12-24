DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS lots;
DROP TABLE IF EXISTS logs;

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE lots (
    id INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    lot_number TEXT NOT NULL,
    expiry_date DATE NOT NULL,
    image TEXT
);

CREATE TABLE logs (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    username TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

INSERT INTO users (username, password_hash, role)
VALUES ('admin', 'pbkdf2:sha256:600000$demo$hashedpassword', 'admin');
