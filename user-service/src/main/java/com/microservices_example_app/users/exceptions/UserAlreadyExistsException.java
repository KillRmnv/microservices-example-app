package com.microservices_example_app.users.exceptions;

/** Registration hit the unique username/email constraint. */
public class UserAlreadyExistsException extends RuntimeException {
    public UserAlreadyExistsException(String message) {
        super(message);
    }
}
