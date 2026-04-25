package com.microservices_example_app.notification.listeners;

import com.microservices_example_app.notification.dto.SuccessfulBookingEvent;
import com.microservices_example_app.notification.service.EmailService;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validator;
import lombok.AllArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import java.util.Set;

@Slf4j
@Component
@AllArgsConstructor
public class BookingKafkaListener {

    private final EmailService emailService;
    private final Validator validator;

    @KafkaListener(
            topics = "${notification.kafka.topic.booking}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "bookingKafkaListenerContainerFactory"
    )
    public void handleSuccessfulBooking(SuccessfulBookingEvent event) {
        log.info("Received booking event: email={}, username={}, event={}, sourceService={}",
                event.getEmail(), event.getUsername(), event.getEvent(), event.getSourceService());

        Set<ConstraintViolation<SuccessfulBookingEvent>> violations = validator.validate(event);
        if (!violations.isEmpty()) {
            log.warn("Invalid booking event received: email={}, violations={}",
                    event.getEmail(),
                    violations.stream().map(ConstraintViolation::getMessage).toList());
            return;
        }

        emailService.sendBookingSuccessEmail(event);
    }
}