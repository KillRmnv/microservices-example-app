package com.microservices_example_app.users.event;

import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.Setter;

@AllArgsConstructor
@Getter
@Setter
public class UserUpdatedEvent {
    @NotNull(message = "User ID must not be null")
    private Integer userId;
    private String email;
    private String username;
    private String role;
    private String sourceService;
}
