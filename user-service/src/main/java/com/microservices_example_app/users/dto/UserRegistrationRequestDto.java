package com.microservices_example_app.users.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.Setter;

@AllArgsConstructor
@Getter

public class UserRegistrationRequestDto {
    private String username;
    private String password;
    private String email;
    private String role;
}
