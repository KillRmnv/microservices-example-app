package com.microservices_example_app.users.exceptions;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.rmi.NoSuchObjectException;
import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandling {
    @ExceptionHandler(NoSuchObjectException.class)
    public ResponseEntity<Map<String, Object>> noSuchObjectException(NoSuchObjectException ex) {
        return ResponseEntity.
                status(HttpStatus.NOT_FOUND).
                body(Map.of("message:",ex.getMessage(),
                        "status",HttpStatus.NOT_FOUND));
    }

    public ResponseEntity<Map<String,Object>> illegalArgumentException(IllegalArgumentException ex){
        return ResponseEntity.
                status(HttpStatus.BAD_REQUEST).
                body(Map.of("message:",ex.getMessage(),
                        "status",HttpStatus.BAD_REQUEST));
    }

}
