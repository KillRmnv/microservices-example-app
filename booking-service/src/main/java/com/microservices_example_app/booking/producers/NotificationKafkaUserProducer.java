package com.microservices_example_app.booking.producers;

import com.microservices_example_app.booking.event.DeleteEventEvent;
import com.microservices_example_app.booking.event.UpdateEventEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class NotificationKafkaUserProducer {
    @Value("${topic.user.mass-mail}")
    private String userExtractingClientTopic;
    private final KafkaTemplate<String, DeleteEventEvent> deleteKafkaTemplate;
    private final KafkaTemplate<String, UpdateEventEvent> updateRefundKafkaTemplate;
    public void sendDeleteEventEvent(DeleteEventEvent event) {
        deleteKafkaTemplate.send(userExtractingClientTopic, event.getEvents().getFirst(), event);
    }

    public void sendUpdateEventEvent(UpdateEventEvent event) {
        updateRefundKafkaTemplate.send(userExtractingClientTopic,event.getEvents().getFirst(), event);
    }
}
