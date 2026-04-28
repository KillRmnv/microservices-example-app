package com.microservices_example_app.users.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.Setter;

@AllArgsConstructor
@Getter
@Setter
public class UserLoginResponseDto {
    @JsonProperty("jwt")
    private String jwt;
    
    @JsonProperty("id")
    private int id;
    
    @JsonProperty("role")
    private String role;
}
