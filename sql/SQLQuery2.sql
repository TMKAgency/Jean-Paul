CREATE TABLE Users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    reset_code VARCHAR(6),
    code_expiration DATETIME
);