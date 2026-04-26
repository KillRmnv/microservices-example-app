package com.microservices_example_app.users.exceptions;

public class EmailForwardingException extends RuntimeException {
    public EmailForwardingException(String message, Throwable ex) {
        super(message, ex);
    }

    public EmailForwardingException(String message) {
        super(message);
    }
}
