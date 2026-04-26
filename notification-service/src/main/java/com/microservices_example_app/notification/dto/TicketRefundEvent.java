package com.microservices_example_app.notification.dto;

import jakarta.validation.constraints.NotBlank;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class TicketRefundEvent {
    @NotBlank(message = "Email must not be blank")
    private String email;

    @NotBlank(message = "Username must not be blank")
    private String username;

    @NotBlank(message = "Event title must not be blank")
    private String eventTitle;

    @NotBlank(message = "Source service must not be blank")
    private String sourceService;
}
