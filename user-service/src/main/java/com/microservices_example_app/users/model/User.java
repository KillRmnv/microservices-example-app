package com.microservices_example_app.users.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "users")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class User extends BaseEntity {

    @Column(nullable = false, unique = true, length = 50)
    protected String username;

    @Column(nullable = false, unique = true, length = 100)
    protected String email;

    @Column(nullable = false, name = "password_hash")
    protected String passwordHash;

    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "role_id", nullable = false)
    protected Role userRole;

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String username;
        private String email;
        private String passwordHash;
        private Role userRole;

        private Builder() {
        }

        public Builder username(String username) {
            if (username == null || username.isBlank()) {
                throw new IllegalArgumentException("Username cannot be null or blank");
            }
            this.username = username;
            return this;
        }

        public Builder email(String email) {
            if (email == null || email.isBlank()) {
                throw new IllegalArgumentException("Email cannot be null or blank");
            }
            if (!email.contains("@")) {
                throw new IllegalArgumentException("Invalid email format");
            }
            this.email = email;
            return this;
        }

        public Builder passwordHash(String passwordHash) {
            if (passwordHash == null || passwordHash.isBlank()) {
                throw new IllegalArgumentException("Password hash cannot be null or blank");
            }
            this.passwordHash = passwordHash;
            return this;
        }

        public Builder userRole(Role userRole) {
            if (userRole == null) {
                throw new IllegalArgumentException("User role cannot be null");
            }
            this.userRole = userRole;
            return this;
        }

        public User build() {
            var user = new User();
            user.username = username;
            user.email = email;
            user.passwordHash = passwordHash;
            user.userRole = userRole;
            return user;
        }
    }
}
