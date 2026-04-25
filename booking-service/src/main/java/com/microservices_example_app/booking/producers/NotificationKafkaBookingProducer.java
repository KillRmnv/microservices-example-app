package com.microservices_example_app.booking.producers;

import com.microservices_example_app.booking.event.SuccessfulBookingEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class NotificationKafkaBookingProducer {
    @Value("${topic.booking}")
    private String bookingClientTopic;

    private final KafkaTemplate<String, Object> kafkaTemplate;

    public void sendSuccessfulEventRegistrationOnEmail(SuccessfulBookingEvent successfulBookingEvent){
        kafkaTemplate.send(bookingClientTopic,successfulBookingEvent.getEmail(),successfulBookingEvent);
    }
}
