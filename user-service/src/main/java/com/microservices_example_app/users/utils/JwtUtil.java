package com.microservices_example_app.users.utils;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;

import java.nio.charset.StandardCharsets;
import java.util.Date;
import javax.crypto.SecretKey;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;

public final class JwtUtil {

    private static String SECRET =
            System.getenv("JWT_SECRET") != null
                    ? System.getenv("JWT_SECRET")
                    : "your-super-secret-key-at-least-32-characters-long!";

    private static Long EXPIRATION =
            System.getenv("JWT_EXPIRATION") != null
                    ? Long.parseLong(System.getenv("JWT_EXPIRATION"))
                    : 3600000L;

    private static SecretKey KEY = Keys.hmacShaKeyFor(
            SECRET.getBytes(StandardCharsets.UTF_8)
    );

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

    public static boolean validateToken(String token) {
        try {
            Jwts.parser().verifyWith(KEY).build().parseSignedClaims(token);
            return true;
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

    public static String extractToken(HttpServletRequest request) {
        String bearer = request.getHeader("Authorization");
        if (bearer != null && bearer.startsWith("Bearer ")) {
            return bearer.substring(7);
        }
        Cookie[] cookies = request.getCookies();
        if (cookies != null) {
            for (Cookie c : cookies) {
                if ("auth_token".equals(c.getName())) return c.getValue();
            }
        }
        return null;
    }
}
