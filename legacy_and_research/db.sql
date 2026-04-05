
-- Drop and create database
DROP DATABASE IF EXISTS Under;
CREATE DATABASE Under;
USE Under;

-- Create users table with name, username, email, password
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50),
    username VARCHAR(50) UNIQUE,
    email VARCHAR(50),
    password VARCHAR(50)
);
