package com.microservices_example_app.notification.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.List;

@AllArgsConstructor
@NoArgsConstructor
@Getter
@Setter
public class MassUpdateEventMailingEvent {
    private List<UserNotificationDto> users;
    private String sourceService;
    private List<String> events;
    private String changesDescription;
}