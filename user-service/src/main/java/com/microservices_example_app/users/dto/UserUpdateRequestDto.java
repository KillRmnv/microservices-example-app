package com.microservices_example_app.users.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
@Schema(description = "Fields to update on an existing user")
public class UserUpdateRequestDto {
    private int id;
    private String username;
    private String email;
    private String role;
    private String password;
    private Boolean isSystem;
}
