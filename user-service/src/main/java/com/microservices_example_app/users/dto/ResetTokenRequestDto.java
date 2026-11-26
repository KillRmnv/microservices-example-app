package com.microservices_example_app.users.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;

@AllArgsConstructor
@Getter
@Schema(description = "Password-reset token validation")
public class ResetTokenRequestDto {
    @NotBlank(message = "Token must not be blank")
    private String token;
}
