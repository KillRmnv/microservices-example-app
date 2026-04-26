package com.microservices_example_app.users.dto;


import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@AllArgsConstructor
@Getter
@NoArgsConstructor
@Setter
public class UserDeleteRequestDto {
    private int id;
    private String username;
    private String email;
    private String role;
}
