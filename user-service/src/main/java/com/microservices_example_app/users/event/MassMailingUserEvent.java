package com.microservices_example_app.users.event;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.List;
@AllArgsConstructor
@NoArgsConstructor
@Getter
@Setter
public class MassMailingUserEvent {
    protected List<UserNotificationDto> users;
    protected String sourceService;
}
