package com.microservices_example_app.notification.listeners;

import com.microservices_example_app.notification.dto.SuccessfulBookingEvent;
import com.microservices_example_app.notification.dto.TicketRefundEvent;
import com.microservices_example_app.notification.service.EmailService;
import com.microservices_example_app.notification.util.KafkaMdc;
import com.microservices_example_app.notification.util.SensitiveMask;
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
        KafkaMdc.begin();
        try {
            log.info("Received booking event: email={}, username={}, event={}, sourceService={}",
                    SensitiveMask.maskEmail(event.getEmail()), event.getUsername(), event.getEvent(), event.getSourceService());

            Set<ConstraintViolation<SuccessfulBookingEvent>> violations = validator.validate(event);
            if (!violations.isEmpty()) {
                log.warn("Invalid booking event received: email={}, violations={}",
                        SensitiveMask.maskEmail(event.getEmail()),
                        violations.stream().map(ConstraintViolation::getMessage).toList());
                return;
            }

            try {
                emailService.sendBookingSuccessEmail(event);
            } catch (Exception e) {
                log.error("Failed to send booking success email to {}: {}", SensitiveMask.maskEmail(event.getEmail()), e.getMessage(), e);
            }
        } finally {
            KafkaMdc.end();
        }
    }

    @KafkaListener(
            topics = "${notification.kafka.topic.ticket-refund}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "ticketRefundKafkaListenerContainerFactory"
    )
    public void handleTicketRefund(TicketRefundEvent event) {
        KafkaMdc.begin();
        try {
            log.info("Refund booking event: email={}, username={}, event={}, sourceService={}",
                    SensitiveMask.maskEmail(event.getEmail()), event.getUsername(), event.getEventTitle(), event.getSourceService());

            Set<ConstraintViolation<TicketRefundEvent>> violations = validator.validate(event);
            if (!violations.isEmpty()) {
                log.warn("Invalid booking event received: email={}, violations={}",
                        SensitiveMask.maskEmail(event.getEmail()),
                        violations.stream().map(ConstraintViolation::getMessage).toList());
                return;
            }

            try {
                emailService.sendTicketRefundEmail(event);
            } catch (Exception e) {
                log.error("Failed to send refund ticket email to {}: {}", SensitiveMask.maskEmail(event.getEmail()), e.getMessage(), e);
            }
        } finally {
            KafkaMdc.end();
        }
    }
}
