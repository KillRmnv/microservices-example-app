package com.microservices_example_app.users.service;

import com.password4j.Password;
import org.springframework.stereotype.Service;
import lombok.extern.slf4j.Slf4j;

/**
  * Implementation of {@link PasswordService} based on password4j (bcrypt).
  * Thread-safe — create a single instance for the entire application.
 */
@Slf4j
@Service
public final class BcryptPasswordService implements PasswordService {


    @Override
    public String hash(String plainPassword) {
        log.debug("Hashing password");
        if (plainPassword == null || plainPassword.isBlank()) {
            throw new IllegalArgumentException("Password cannot be empty or consist of only whitespace");
        }

        return Password.hash(plainPassword)
                .withBcrypt()
                .getResult();
    }

    @Override
    public boolean verify(String plainPassword, String storedHash) {
        if (plainPassword == null || storedHash == null || storedHash.isBlank()) {
            return false;
        }

        return Password.check(plainPassword, storedHash)
                .withBcrypt();
    }
}