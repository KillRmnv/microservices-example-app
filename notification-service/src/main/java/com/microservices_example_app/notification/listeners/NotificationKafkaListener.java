package com.microservices_example_app.notification.listeners;

import com.microservices_example_app.notification.dto.ForgetPasswordEvent;
import com.microservices_example_app.notification.dto.SuccessfulRegistrationEmailEvent;
import com.microservices_example_app.notification.service.EmailService;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validator;
import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaHandler;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import java.util.Set;

@Slf4j
@Component
@AllArgsConstructor

public class NotificationKafkaListener {

    private final EmailService emailService;
    private final Validator validator;

    @KafkaListener(
            topics = "${notification.kafka.topic.authentication}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "successfulRegistrationKafkaListenerContainerFactory"
    )
    public void handleSuccessfulRegistration(SuccessfulRegistrationEmailEvent event) {
        log.info("Received successful registration event: email={}, username={}, sourceService={}",
                event.getEmail(), event.getUsername(), event.getSourceService());

        Set<ConstraintViolation<SuccessfulRegistrationEmailEvent>> violations = validator.validate(event);
        if (!violations.isEmpty()) {
            log.warn("Invalid successful registration event received: email={}, violations={}",
                    event.getEmail(),
                    violations.stream().map(ConstraintViolation::getMessage).toList());
            return;
        }

        try {
            emailService.sendSuccessfulRegistrationEmail(event);
        } catch (Exception e) {
            log.error("Failed to send successful registration email to {}: {}", event.getEmail(), e.getMessage(), e);
        }
    }

    @KafkaListener(
            topics = "${notification.kafka.topic.authentication}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "forgetPasswordKafkaListenerContainerFactory"
    )
    public void handleForgetPassword(ForgetPasswordEvent event) {
        log.info("Received forget password event: email={}, sourceService={}",
                event.getEmail(), event.getSourceService());

        Set<ConstraintViolation<ForgetPasswordEvent>> violations = validator.validate(event);
        if (!violations.isEmpty()) {
            log.warn("Invalid forget password event received: email={}, violations={}",
                    event.getEmail(),
                    violations.stream().map(ConstraintViolation::getMessage).toList());
            return;
        }

        try {
            emailService.sendForgetPasswordEmail(event);
        } catch (Exception e) {
            log.error("Failed to send forget password email to {}: {}", event.getEmail(), e.getMessage(), e);
        }
    }

//    @KafkaListener(
//            topics = "${notification.kafka.topic.authentication}",
//            groupId = "${spring.kafka.consumer.group-id}",
//            containerFactory = "authenticationKafkaListenerContainerFactory"
//    )
//    public void handleUnknown(Object event) {
//        log.warn("Received unknown authentication event type: {}", event);
//    }
}