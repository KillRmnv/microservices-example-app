package com.microservices_example_app.users.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;

@AllArgsConstructor
@Getter
public class UserLoginRequestDto {
    @NotBlank(message = "Email must not be blank")
    @Email(message = "Email must be valid")
    private String email;
    @NotBlank(message = "Password must not be blank")
    private String password;
}
