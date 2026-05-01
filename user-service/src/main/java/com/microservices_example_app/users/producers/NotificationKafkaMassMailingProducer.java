package com.microservices_example_app.users.producers;

import com.microservices_example_app.users.event.MassDeleteEventMailingEvent;
import com.microservices_example_app.users.event.MassUpdateEventMailingEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
@Slf4j
@RequiredArgsConstructor
public class NotificationKafkaMassMailingProducer {

    @Value("${topic.notification.mass-mailing}")
    private String massMailingTopic;

    private final KafkaTemplate<String, MassDeleteEventMailingEvent> massDeleteKafkaTemplate;
    private final KafkaTemplate<String, MassUpdateEventMailingEvent> massUpdateKafkaTemplate;

    public void sendMassDeleteEventMailing(MassDeleteEventMailingEvent event) {
        log.info("Sending MassDeleteEventMailingEvent: {} users, {} events",
                event.getUsers() != null ? event.getUsers().size() : 0,
                event.getEvents() != null ? event.getEvents().size() : 0);
        massDeleteKafkaTemplate.send(massMailingTopic, event);
    }

    public void sendMassUpdateEventMailing(MassUpdateEventMailingEvent event) {
        log.info("Sending MassUpdateEventMailingEvent: {} users, {} events",
                event.getUsers() != null ? event.getUsers().size() : 0,
                event.getEvents() != null ? event.getEvents().size() : 0);
        massUpdateKafkaTemplate.send(massMailingTopic, event);
    }
}