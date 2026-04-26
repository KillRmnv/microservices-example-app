package com.microservices_example_app.users.exceptions;

import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.Logger;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.rmi.NoSuchObjectException;
import java.util.Map;
import java.util.stream.Collectors;
@Slf4j
@RestControllerAdvice
@AllArgsConstructor
public class GlobalExceptionHandling {


    @ExceptionHandler(NoSuchObjectException.class)
    public ResponseEntity<Map<String, Object>> noSuchObjectException(NoSuchObjectException ex) {
        log.warn("NotFoundException:{}",ex.getMessage());
        return ResponseEntity.
                status(HttpStatus.NOT_FOUND).
                body(Map.of("message",ex.getMessage(),
                        "status",HttpStatus.NOT_FOUND));
    }
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String,Object>> illegalArgumentException(IllegalArgumentException ex){
        log.warn("IllegalArgumentException:{}",ex.getMessage());
        return ResponseEntity.
                status(HttpStatus.BAD_REQUEST).
                body(Map.of("message",ex.getMessage(),
                        "status",HttpStatus.BAD_REQUEST));
    }
    @ExceptionHandler(EmailForwardingException.class)
    public ResponseEntity<Map<String,Object>> emailForwardingException(EmailForwardingException ex){
        log.warn("EmailForwardingException exception:{}",ex.getMessage());
        return ResponseEntity.
                status(HttpStatus.INTERNAL_SERVER_ERROR).
                body(Map.of("message",ex.getMessage(),
                        "status",HttpStatus.INTERNAL_SERVER_ERROR));
    }
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> validationException(MethodArgumentNotValidException ex) {
        Map<String, String> errors = ex.getBindingResult().getFieldErrors().stream()
                .collect(Collectors.toMap(
                        error -> error.getField(),
                        error -> error.getDefaultMessage() != null ? error.getDefaultMessage() : "Invalid value",
                        (first, second) -> first
                ));
        log.warn("Validation error: {}", errors);
        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(Map.of(
                        "status", HttpStatus.BAD_REQUEST,
                        "message", "Validation failed",
                        "errors", errors
                ));
    }
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String,Object>> unexpectedException(Exception ex){
        log.warn("Unknown exception:{}",ex.getMessage());
        return ResponseEntity.
                status(HttpStatus.INTERNAL_SERVER_ERROR).
                body(Map.of("message",ex.getMessage(),
                        "status",HttpStatus.INTERNAL_SERVER_ERROR));
    }

}
