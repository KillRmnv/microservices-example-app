package com.microservices_example_app.notification.exceptions;

public class EmailSendingException extends RuntimeException {
    public EmailSendingException(String message) {
        super(message);
    }
    public EmailSendingException(String message,Exception ex){
        super(message,ex);
    }
}
