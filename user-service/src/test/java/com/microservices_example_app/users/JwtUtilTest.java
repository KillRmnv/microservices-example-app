package com.microservices_example_app.users;

import com.microservices_example_app.users.utils.JwtUtil;
import io.jsonwebtoken.Claims;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class JwtUtilTest {


    @Test
    void generateToken_shouldProduceValidToken() {
        String token = JwtUtil.generateToken(1, "alex", "alex@test.com", "CUSTOMER");

        assertThat(JwtUtil.validateToken(token)).isTrue();
    }

    @Test
    void validateToken_shouldReturnFalseForInvalidToken() {
        assertThat(JwtUtil.validateToken("garbage.token.value")).isFalse();
    }

    @Test
    void validateToken_shouldReturnFalseForEmptyString() {
        assertThat(JwtUtil.validateToken("")).isFalse();
    }


    @Test
    void generatePasswordResetToken_shouldProduceValidToken() {
        String token = JwtUtil.generatePasswordResetToken(10, "alex@test.com");

        assertThat(JwtUtil.validatePasswordResetToken(token)).isTrue();
    }

    @Test
    void validatePasswordResetToken_shouldReturnFalseForInvalidToken() {
        assertThat(JwtUtil.validatePasswordResetToken("garbage.token.value")).isFalse();
    }

    @Test
    void validatePasswordResetToken_shouldReturnFalseForRegularToken() {
        String regularToken = JwtUtil.generateToken(1, "alex", "alex@test.com", "CUSTOMER");

        assertThat(JwtUtil.validatePasswordResetToken(regularToken)).isFalse();
    }


    @Test
    void parseToken_shouldReturnClaimsForValidToken() {
        String token = JwtUtil.generateToken(5, "bob", "bob@test.com", "ADMIN");

        Claims claims = JwtUtil.parseToken(token);

        assertThat(claims.getSubject()).isEqualTo("bob");
        assertThat(claims.get("email", String.class)).isEqualTo("bob@test.com");
        assertThat(claims.get("role", String.class)).isEqualTo("ADMIN");
        assertThat(claims.get("id", Integer.class)).isEqualTo(5);
    }

    @Test
    void parseToken_shouldThrowForInvalidToken() {
        assertThatThrownBy(() -> JwtUtil.parseToken("invalid"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Invalid token");
    }


    @Test
    void parsePasswordResetToken_shouldReturnClaimsForValidToken() {
        String token = JwtUtil.generatePasswordResetToken(10, "alex@test.com");

        Claims claims = JwtUtil.parsePasswordResetToken(token);

        assertThat(claims.getSubject()).isEqualTo("alex@test.com");
        assertThat(claims.get("id", Integer.class)).isEqualTo(10);
        assertThat(claims.get("purpose", String.class)).isEqualTo("password_reset");
    }

    @Test
    void parsePasswordResetToken_shouldThrowForInvalidToken() {
        assertThatThrownBy(() -> JwtUtil.parsePasswordResetToken("invalid"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Invalid reset token");
    }


    @Test
    void extractUserIdFromPasswordResetToken_shouldReturnId() {
        String token = JwtUtil.generatePasswordResetToken(42, "test@test.com");

        Integer userId = JwtUtil.extractUserIdFromPasswordResetToken(token);

        assertThat(userId).isEqualTo(42);
    }

    @Test
    void extractUserIdFromPasswordResetToken_shouldThrowForInvalidToken() {
        assertThatThrownBy(() -> JwtUtil.extractUserIdFromPasswordResetToken("bad"))
                .isInstanceOf(IllegalArgumentException.class);
    }


    @Test
    void extractRoleFromToken_shouldReturnRole() {
        String token = JwtUtil.generateToken(1, "alex", "alex@test.com", "EVENT_MANAGER");

        String role = JwtUtil.extractRoleFromToken(token);

        assertThat(role).isEqualTo("EVENT_MANAGER");
    }

    @Test
    void extractRoleFromToken_shouldThrowForInvalidToken() {
        assertThatThrownBy(() -> JwtUtil.extractRoleFromToken("bad"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Invalid token");
    }

    @Test
    void extractSubjectFromToken_shouldReturnUsername() {
        String token = JwtUtil.generateToken(1, "alex", "alex@test.com", "CUSTOMER");

        String subject = JwtUtil.extractSubjectFromToken(token);

        assertThat(subject).isEqualTo("alex");
    }

    @Test
    void extractSubjectFromToken_shouldThrowForInvalidToken() {
        assertThatThrownBy(() -> JwtUtil.extractSubjectFromToken("bad"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("Invalid token");
    }


    @Test
    void extractToken_shouldExtractFromBearerHeader() {
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getHeader("Authorization")).thenReturn("Bearer my-jwt-token");
        when(request.getCookies()).thenReturn(null);

        String token = JwtUtil.extractToken(request);

        assertThat(token).isEqualTo("my-jwt-token");
    }

    @Test
    void extractToken_shouldFallbackToCookie() {
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getHeader("Authorization")).thenReturn(null);

        Cookie cookie = new Cookie("auth_token", "cookie-jwt-token");
        when(request.getCookies()).thenReturn(new Cookie[]{cookie});

        String token = JwtUtil.extractToken(request);

        assertThat(token).isEqualTo("cookie-jwt-token");
    }

    @Test
    void extractToken_shouldReturnNullWhenNoToken() {
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getHeader("Authorization")).thenReturn(null);
        when(request.getCookies()).thenReturn(null);

        String token = JwtUtil.extractToken(request);

        assertThat(token).isNull();
    }

    @Test
    void extractToken_shouldReturnNullWhenNoCookies() {
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getHeader("Authorization")).thenReturn(null);
        when(request.getCookies()).thenReturn(new Cookie[]{});

        String token = JwtUtil.extractToken(request);

        assertThat(token).isNull();
    }

    @Test
    void extractToken_shouldIgnoreNonAuthTokenCookie() {
        HttpServletRequest request = mock(HttpServletRequest.class);
        when(request.getHeader("Authorization")).thenReturn(null);

        Cookie cookie = new Cookie("other_token", "some-value");
        when(request.getCookies()).thenReturn(new Cookie[]{cookie});

        String token = JwtUtil.extractToken(request);

        assertThat(token).isNull();
    }
}
