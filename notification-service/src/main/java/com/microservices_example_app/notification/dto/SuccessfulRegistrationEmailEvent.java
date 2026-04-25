package com.microservices_example_app.notification.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class SuccessfulRegistrationEmailEvent {
    @NotBlank(message = "Email must not be blank")
    private String email;

    @NotBlank(message = "Source service must not be blank")
    private String sourceService;

    @NotBlank(message = "Username must not be blank")
    private String username;
}