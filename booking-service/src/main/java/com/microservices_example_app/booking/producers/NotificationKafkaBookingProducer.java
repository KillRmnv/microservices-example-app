package com.microservices_example_app.booking.producers;

import com.microservices_example_app.booking.event.DeleteEventEvent;
import com.microservices_example_app.booking.event.SuccessfulBookingEvent;
import com.microservices_example_app.booking.event.SuccessfulTicketRefundEvent;
import com.microservices_example_app.booking.event.UpdateEventEvent;
import com.microservices_example_app.booking.utils.TransactionalEventPublisher;
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

    private final KafkaTemplate<String, SuccessfulBookingEvent> bookingKafkaTemplate;
    private final KafkaTemplate<String, SuccessfulTicketRefundEvent> ticketRefundKafkaTemplate;
    private final TransactionalEventPublisher transactionalEventPublisher;

    public void sendSuccessfulBookingEvent(SuccessfulBookingEvent event) {
        transactionalEventPublisher.sendAfterCommit(bookingKafkaTemplate, bookingClientTopic, event.getEmail(), event);
    }

    public void sendSuccessfulTicketRefundEvent(SuccessfulTicketRefundEvent event) {
        transactionalEventPublisher.sendAfterCommit(ticketRefundKafkaTemplate, ticketRefundTopic, event.getEmail(), event);
    }

}
