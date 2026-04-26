package com.microservices_example_app.booking.producers;

import com.microservices_example_app.booking.event.SuccessfulBookingEvent;
import com.microservices_example_app.booking.event.SuccessfulTicketRefundEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class NotificationKafkaBookingProducer {

    @Value("${topic.booking}")
    private String bookingClientTopic;

    @Value("${topic.ticket-refund}")
    private String ticketRefundTopic;

    private final KafkaTemplate<String, Object> kafkaTemplate;

    public void sendSuccessfulBookingEvent(SuccessfulBookingEvent event) {
        kafkaTemplate.send(bookingClientTopic, event.getEmail(), event);
    }

    public void sendSuccessfulTicketRefundEvent(SuccessfulTicketRefundEvent event) {
        kafkaTemplate.send(ticketRefundTopic, event.getEmail(), event);
    }
}