package com.microservices_example_app.users.producers;

import com.microservices_example_app.users.event.ForgetPasswordEvent;
import com.microservices_example_app.users.event.SuccessfulRegistrationEmailEvent;
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

    private final KafkaTemplate<String, ForgetPasswordEvent> resetPasswordKafkaTemplate;
    private final KafkaTemplate<String, SuccessfulRegistrationEmailEvent> registrationKafkaTemplate;

    public void sendEmailToRestorePassword(ForgetPasswordEvent forgetPasswordEvent) {
        resetPasswordKafkaTemplate.send(authenticationClientTopic, forgetPasswordEvent.getEmail(), forgetPasswordEvent);
    }

    public void sendSuccessfulRegistrationEmail(SuccessfulRegistrationEmailEvent successfulRegistrationEmailEvent) {
        registrationKafkaTemplate.send(authenticationClientTopic, successfulRegistrationEmailEvent.getEmail(), successfulRegistrationEmailEvent);
    }
}
