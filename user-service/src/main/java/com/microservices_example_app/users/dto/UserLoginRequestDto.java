package com.microservices_example_app.users.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;

@AllArgsConstructor
@Getter

public class UserLoginRequestDto {
    private String email;
    private String password;
}
