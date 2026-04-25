package com.microservices_example_app.users.service;

import com.password4j.Password;

/**
  * Interface for password hashing and verification.
  *
  * <p>Abstracts the specific hashing library (password4j),
  * allowing the implementation to be easily replaced in the future.</p>
 */
public interface PasswordService {

     /**
      * Hashes a plain text password.
      *
      * @param plainPassword plain text password
      * @return hash in the form $2b$12$...
      */
    String hash(String plainPassword);

     /**
      * Verifies a plain text password against a stored hash.
      *
      * @param plainPassword plain text password
      * @param storedHash    hash from DB
      * @return true if the password matches
      */
    boolean verify(String plainPassword, String storedHash);
}
