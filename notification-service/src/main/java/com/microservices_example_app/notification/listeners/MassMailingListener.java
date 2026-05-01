package com.microservices_example_app.notification.listeners;

import com.microservices_example_app.notification.dto.MassDeleteEventMailingEvent;
import com.microservices_example_app.notification.dto.MassUpdateEventMailingEvent;
import com.microservices_example_app.notification.service.MassMailingEmailService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class MassMailingListener {

    private final MassMailingEmailService massMailingEmailService;

    @KafkaListener(
            topics = "${notification.kafka.topic.mass-mailing}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "massDeleteKafkaListenerContainerFactory"
    )
    public void handleMassDeleteEvent(MassDeleteEventMailingEvent event) {
        log.info("Received MassDeleteEventMailingEvent: {} users, sourceService={}",
                event.getUsers().size(), event.getSourceService());
        massMailingEmailService.sendMassDeleteEventMailing(event);
    }

    @KafkaListener(
            topics = "${notification.kafka.topic.mass-mailing}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "massUpdateKafkaListenerContainerFactory"
    )
    public void handleMassUpdateEvent(MassUpdateEventMailingEvent event) {
        log.info("Received MassUpdateEventMailingEvent: {} users, sourceService={}",
                event.getUsers().size(), event.getSourceService());
        massMailingEmailService.sendMassUpdateEventMailing(event);
    }
}