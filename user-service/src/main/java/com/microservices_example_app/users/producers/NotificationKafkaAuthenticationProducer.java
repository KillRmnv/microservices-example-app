package com.microservices_example_app.users.producers;

import com.microservices_example_app.users.event.ForgetPasswordEvent;
import com.microservices_example_app.users.event.SuccessfulRegistrationEmailEvent;
import com.microservices_example_app.users.event.UserDeletedEvent;
import com.microservices_example_app.users.event.UserUpdatedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
@Slf4j
@RequiredArgsConstructor
public class NotificationKafkaAuthenticationProducer {
    @Value("${topic.authentication}")
    private String authenticationClientTopic;

    @Value("${topic.user-lifecycle:notification.user-lifecycle}")
    private String userLifecycleTopic;
    @Value("${topic.forget-password}")
    private String forgetPasswordTopic;

    private final KafkaTemplate<String, ForgetPasswordEvent> resetPasswordKafkaTemplate;
    private final KafkaTemplate<String, SuccessfulRegistrationEmailEvent> registrationKafkaTemplate;
    private final KafkaTemplate<String, UserDeletedEvent> userDeletedKafkaTemplate;
    private final KafkaTemplate<String, UserUpdatedEvent> userUpdatedKafkaTemplate;

    public void sendEmailToRestorePassword(ForgetPasswordEvent forgetPasswordEvent) {
        resetPasswordKafkaTemplate.send(forgetPasswordTopic, forgetPasswordEvent.getEmail(), forgetPasswordEvent);
    }

    public void sendSuccessfulRegistrationEmail(SuccessfulRegistrationEmailEvent successfulRegistrationEmailEvent) {
        registrationKafkaTemplate.send(authenticationClientTopic, successfulRegistrationEmailEvent.getEmail(), successfulRegistrationEmailEvent);
    }

    public void sendUserDeletedEvent(UserDeletedEvent event) {
        userDeletedKafkaTemplate.send(userLifecycleTopic, event.getUserId().toString(), event);
    }

    public void sendUserUpdatedEvent(UserUpdatedEvent event) {
        userUpdatedKafkaTemplate.send(userLifecycleTopic, event.getUserId().toString(), event);
    }
}
