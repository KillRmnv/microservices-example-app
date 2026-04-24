package com.microservices_example_app.users.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.Setter;

@AllArgsConstructor
@Getter
@Setter
public class UserLoginResponseDto {
    private String jwt;
    private int id;
}
