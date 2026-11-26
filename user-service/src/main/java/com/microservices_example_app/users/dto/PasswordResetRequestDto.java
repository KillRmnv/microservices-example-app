package com.microservices_example_app.users.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Getter;

@AllArgsConstructor
@Getter
@Schema(description = "Password reset with a one-time token")
public class PasswordResetRequestDto {
    @NotBlank(message = "Token must not be blank")
    private String token;
    @NotBlank(message = "New password must not be blank")
    @Size(min = 6, message = "Password must be at least 6 characters")
    private String newPassword;
}
