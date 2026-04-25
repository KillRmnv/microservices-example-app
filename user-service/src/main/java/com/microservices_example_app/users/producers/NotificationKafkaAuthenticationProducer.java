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

    private final KafkaTemplate<String, Object> kafkaTemplate;

    public void sendEmailToRestorePassword(ForgetPasswordEvent forgetPasswordEvent) {
        kafkaTemplate.send(authenticationClientTopic, forgetPasswordEvent.getEmail(), forgetPasswordEvent);
    }

    public void sendSuccessfulRegistrationEmail(SuccessfulRegistrationEmailEvent succsessfulRegistrationEmailEvent) {
        kafkaTemplate.send(authenticationClientTopic, succsessfulRegistrationEmailEvent.getEmail(), succsessfulRegistrationEmailEvent);
    }
}
