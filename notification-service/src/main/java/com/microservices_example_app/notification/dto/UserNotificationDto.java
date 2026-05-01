// UserNotificationDto.java
package com.microservices_example_app.notification.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@AllArgsConstructor
@NoArgsConstructor
@Getter
@Setter
public class UserNotificationDto {
    private String email;
    private String username;
}