package com.microservices_example_app.booking.exceptions;

import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.Logger;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;
@Slf4j
@AllArgsConstructor
@RestControllerAdvice
public class GlobalControllerAdvice {
    private Logger logger;
    @ExceptionHandler(NotFoundException.class)
    public ResponseEntity<Map<String, Object>> notFoundException(NotFoundException ex) {
        logger.warn("NotFoundException:{}",ex.getMessage());
        return ResponseEntity.
                status(HttpStatus.NOT_FOUND).
                body(Map.of("status", HttpStatus.NOT_FOUND,
                        "message", ex.getMessage()));

    }
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String,Object>> illegalArgumentException(IllegalArgumentException ex){
        logger.warn("IllegalArgumentException:{}",ex.getMessage());
        return ResponseEntity.
                status(HttpStatus.BAD_REQUEST).
                body(Map.of("message",ex.getMessage(),
                        "status",HttpStatus.BAD_REQUEST));
    }
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String,Object>> unexpectedException(Exception ex){
        logger.warn("Unknown exception:{}",ex.getMessage());
        return ResponseEntity.
                status(HttpStatus.INTERNAL_SERVER_ERROR).
                body(Map.of("message",ex.getMessage(),
                        "status",HttpStatus.INTERNAL_SERVER_ERROR));
    }
}
