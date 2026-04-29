package com.microservices_example_app.users.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class UserUpdateRequestDto {
    private int id;
    private String username;
    private String email;
    private String role;
    private String password;
    private Boolean isSystem;
}
