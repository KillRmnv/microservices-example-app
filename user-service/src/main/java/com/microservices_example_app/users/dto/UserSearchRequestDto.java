package com.microservices_example_app.users.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@AllArgsConstructor
@Getter
@NoArgsConstructor
@Setter
@Schema(description = "Filter for searching users")
public class UserSearchRequestDto {
    private Long id;
    private String username;
    private String email;
    private String role;
}
