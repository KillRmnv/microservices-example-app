package com.microservices_example_app.booking.utils;

import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class JwtRequestUserExtractor {

    private final HttpServletRequest request;

    public String extractEmail() {
        String token = JwtBookingUtil.extractToken(request);
        if (token == null || !JwtBookingUtil.validateToken(token)) {
            throw new IllegalArgumentException("Invalid or missing JWT token");
        }
        return JwtBookingUtil.extractEmail(token);
    }

    public String extractUsername() {
        String token = JwtBookingUtil.extractToken(request);
        if (token == null || !JwtBookingUtil.validateToken(token)) {
            throw new IllegalArgumentException("Invalid or missing JWT token");
        }
        return JwtBookingUtil.extractUsername(token);
    }

    public Integer extractUserId() {
        String token = JwtBookingUtil.extractToken(request);
        if (token == null || !JwtBookingUtil.validateToken(token)) {
            throw new IllegalArgumentException("Invalid or missing JWT token");
        }
        return JwtBookingUtil.extractUserId(token);
    }
}