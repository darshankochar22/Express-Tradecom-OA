CREATE DATABASE IF NOT EXISTS users
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE users;

CREATE TABLE IF NOT EXISTS users (
  id    INT          NOT NULL AUTO_INCREMENT,
  name  VARCHAR(100) NOT NULL,
  email VARCHAR(255) NOT NULL,
  role  VARCHAR(50)  NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB;
