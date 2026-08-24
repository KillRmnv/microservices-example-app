package com.microservices_example_app.booking.utils;

import io.jsonwebtoken.Claims;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class JwtRequestUserExtractor {

    private final HttpServletRequest request;

    private Claims getClaims() {
        String token = JwtBookingUtil.extractToken(request);
        if (token == null || !JwtBookingUtil.validateToken(token)) {
            throw new IllegalArgumentException("Invalid or missing JWT token");
        }
        return JwtBookingUtil.parseToken(token);
    }

    public String extractEmail() {
        return getClaims().get("email", String.class);
    }

    public String extractUsername() {
        return getClaims().getSubject();
    }

    public Integer extractUserId() {
        return getClaims().get("id", Integer.class);
    }

    public String extractRole() {
        String headerRole = request.getHeader("X-User-Role");
        if (headerRole != null && !headerRole.isBlank()) {
            return headerRole;
        }
        return getClaims().get("role", String.class);
    }

    public boolean isEventManagerOrAdmin() {
        String role = extractRole();
        return "EVENT_MANAGER".equals(role) || "ADMIN".equals(role);
    }

    public boolean isAdmin() {
        return "ADMIN".equals(extractRole());
    }
}