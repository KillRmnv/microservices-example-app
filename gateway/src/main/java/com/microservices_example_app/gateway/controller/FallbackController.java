package com.microservices_example_app.gateway.controller;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import lombok.extern.slf4j.Slf4j;

import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/fallback")
public class FallbackController {

    @GetMapping("/users")
    public ResponseEntity<?> usersFallback() {
        log.warn("Users service is unavailable, triggering fallback");
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of(
                        "status", 503,
                        "error", "Service Unavailable",
                        "message", "Users service is temporarily unavailable"
                ));
    }

    @GetMapping("/booking")
    public ResponseEntity<?> bookingFallback() {
        log.warn("Booking service is unavailable, triggering fallback");
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)
                .body(Map.of(
                        "status", 503,
                        "error", "Service Unavailable",
                        "message", "Booking service is temporarily unavailable"
                ));
    }
}