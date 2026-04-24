package com.microservices_example_app.users.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.Setter;

@AllArgsConstructor
@Getter

public class UserSerchRequestDto {
    private int id;
    private String username;
    private String email;
    private String role;
}
