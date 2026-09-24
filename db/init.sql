CREATE DATABASE IF NOT EXISTS users
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE users;

CREATE TABLE IF NOT EXISTS users (
  id                 INT          NOT NULL AUTO_INCREMENT,
  name               VARCHAR(100) NOT NULL,
  email              VARCHAR(255) NOT NULL,
  role               VARCHAR(50)  NOT NULL,
  password_hash      VARCHAR(255) NOT NULL,
  date_of_birth      DATE         NOT NULL,
  token_version      INT          NOT NULL DEFAULT 0,
  reset_attempts     INT          NOT NULL DEFAULT 0,
  reset_locked_until DATETIME     NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;
