package com.microservices_example_app.users.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;

@AllArgsConstructor
@Getter
@Schema(description = "Password-reset request")
public class EmailRequestDto {
    @NotBlank(message = "Email must not be blank")
    @Email(message = "Email must be valid")
    private String email;
}
