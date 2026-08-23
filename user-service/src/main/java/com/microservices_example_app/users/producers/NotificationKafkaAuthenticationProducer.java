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
        resetPasswordKafkaTemplate.send(forgetPasswordTopic, forgetPasswordEvent.getEmail(), forgetPasswordEvent)
                .whenComplete((result, ex) -> {
                    if (ex != null) log.error("Failed to send forget-password event: {}", ex.getMessage());
                    else log.debug("Forget-password event sent to partition={}", result.getRecordMetadata().partition());
                });
    }

    public void sendSuccessfulRegistrationEmail(SuccessfulRegistrationEmailEvent successfulRegistrationEmailEvent) {
        registrationKafkaTemplate.send(authenticationClientTopic, successfulRegistrationEmailEvent.getEmail(), successfulRegistrationEmailEvent)
                .whenComplete((result, ex) -> {
                    if (ex != null) log.error("Failed to send registration event: {}", ex.getMessage());
                    else log.debug("Registration event sent to partition={}", result.getRecordMetadata().partition());
                });
    }

    public void sendUserDeletedEvent(UserDeletedEvent event) {
        userDeletedKafkaTemplate.send(userLifecycleTopic, event.getUserId().toString(), event)
                .whenComplete((result, ex) -> {
                    if (ex != null) log.error("Failed to send user-deleted event: {}", ex.getMessage());
                    else log.debug("User-deleted event sent to partition={}", result.getRecordMetadata().partition());
                });
    }

    public void sendUserUpdatedEvent(UserUpdatedEvent event) {
        userUpdatedKafkaTemplate.send(userLifecycleTopic, event.getUserId().toString(), event)
                .whenComplete((result, ex) -> {
                    if (ex != null) log.error("Failed to send user-updated event: {}", ex.getMessage());
                    else log.debug("User-updated event sent to partition={}", result.getRecordMetadata().partition());
                });
    }
}
