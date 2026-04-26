package com.microservices_example_app.users.utils;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

public final class JwtUtil {

    private static final String SECRET =
            System.getenv("JWT_SECRET") != null
                    ? System.getenv("JWT_SECRET")
                    : "your-super-secret-key-at-least-32-characters-long!";

    private static final long EXPIRATION =
            System.getenv("JWT_EXPIRATION") != null
                    ? Long.parseLong(System.getenv("JWT_EXPIRATION"))
                    : 3600000L;

    private static final String RESET_SECRET =
            System.getenv("JWT_RESET_SECRET") != null
                    ? System.getenv("JWT_RESET_SECRET")
                    : "your-reset-secret-key-at-least-32-characters-long!!";

    private static final long RESET_EXPIRATION =
            System.getenv("JWT_RESET_EXPIRATION") != null
                    ? Long.parseLong(System.getenv("JWT_RESET_EXPIRATION"))
                    : 900000L;

    private static final SecretKey KEY = Keys.hmacShaKeyFor(
            SECRET.getBytes(StandardCharsets.UTF_8)
    );

    private static final SecretKey RESET_KEY = Keys.hmacShaKeyFor(
            RESET_SECRET.getBytes(StandardCharsets.UTF_8)
    );

    private JwtUtil() {
    }

    public static String generateToken(
            int id,
            String username,
            String email,
            String roleName
    ) {
        return Jwts.builder()
                .expiration(new Date(System.currentTimeMillis() + EXPIRATION))
                .issuedAt(new Date())
                .subject(username)
                .claim("email", email)
                .claim("role", roleName)
                .claim("id", id)
                .signWith(KEY)
                .compact();
    }

    public static String generatePasswordResetToken(int id, String email) {
        return Jwts.builder()
                .subject(email)
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + RESET_EXPIRATION))
                .claim("id", id)
                .claim("purpose", "password_reset")
                .signWith(RESET_KEY)
                .compact();
    }

    public static boolean validateToken(String token) {
        try {
            Jwts.parser().verifyWith(KEY).build().parseSignedClaims(token);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    public static boolean validatePasswordResetToken(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(RESET_KEY)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            return "password_reset".equals(claims.get("purpose", String.class));
        } catch (Exception e) {
            return false;
        }
    }

    public static Claims parseToken(String token) {
        try {
            return Jwts.parser()
                    .verifyWith(KEY)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
        } catch (Exception e) {
            throw new IllegalArgumentException("Invalid token");
        }
    }

    public static Claims parsePasswordResetToken(String token) {
        try {
            return Jwts.parser()
                    .verifyWith(RESET_KEY)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();
        } catch (Exception e) {
            throw new IllegalArgumentException("Invalid reset token");
        }
    }

    public static Integer extractUserIdFromPasswordResetToken(String token) {
        Claims claims = parsePasswordResetToken(token);
        return claims.get("id", Integer.class);
    }

    public static String extractRoleFromToken(String token) {
        Claims claims = parseToken(token);
        return claims.get("role", String.class);
    }

    public static String extractSubjectFromToken(String token) {
        Claims claims = parseToken(token);
        return claims.getSubject();
    }

    public static long getExpirationMillis() {
        return EXPIRATION;
    }

    public static long getResetExpirationMillis() {
        return RESET_EXPIRATION;
    }

    public static String extractToken(HttpServletRequest request) {
        String bearer = request.getHeader("Authorization");
        if (bearer != null && bearer.startsWith("Bearer ")) {
            return bearer.substring(7);
        }

        Cookie[] cookies = request.getCookies();
        if (cookies != null) {
            for (Cookie c : cookies) {
                if ("auth_token".equals(c.getName())) {
                    return c.getValue();
                }
            }
        }

        return null;
    }
}