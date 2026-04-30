package com.microservices_example_app.notification.dto;

import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class UserDeletedEvent {
    @NotNull(message = "User ID must not be null")
    private Integer userId;
    private String email;
    private String username;
    private String sourceService;
}
