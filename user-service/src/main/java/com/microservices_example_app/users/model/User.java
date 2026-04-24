package com.microservices_example_app.users.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.*;

@Entity
@Table(name = "users")
@Getter
@Builder
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor(access = AccessLevel.PROTECTED)
public class User extends BaseEntity {
    
    @NotBlank(message = "Username can not be blank")
    @Column(nullable = false, unique = true, length = 50)
    protected String username;
    @NotBlank(message = "Email can not be blank")
    @Email
    @Column(nullable = false, unique = true, length = 100)
    protected String email;
    @NotBlank(message = "PasswordHash can not be blank")
    @Column(nullable = false, name = "password_hash")
    protected String passwordHash;
    @NotNull(message = "Role can not be null")
    @ManyToOne(fetch = FetchType.EAGER)
    @JoinColumn(name = "role_id", nullable = false)
    protected Role userRole;
}
