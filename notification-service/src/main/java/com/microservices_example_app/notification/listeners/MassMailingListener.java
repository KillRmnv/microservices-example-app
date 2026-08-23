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
            groupId = "${spring.kafka.consumer.group-id}-delete",
            containerFactory = "massDeleteKafkaListenerContainerFactory"
    )
    public void handleMassDeleteEvent(MassDeleteEventMailingEvent event) {
        log.info("Received MassDeleteEventMailingEvent: {} users, sourceService={}",
                event.getUsers().size(), event.getSourceService());
        try {
            massMailingEmailService.sendMassDeleteEventMailing(event);
        } catch (Exception e) {
            log.error("Failed to send mass delete mailing: {}", e.getMessage(), e);
        }
    }

    @KafkaListener(
            topics = "${notification.kafka.topic.mass-mailing}",
            groupId = "${spring.kafka.consumer.group-id}-update",
            containerFactory = "massUpdateKafkaListenerContainerFactory"
    )
    public void handleMassUpdateEvent(MassUpdateEventMailingEvent event) {
        log.info("Received MassUpdateEventMailingEvent: {} users, sourceService={}",
                event.getUsers().size(), event.getSourceService());
        try {
            massMailingEmailService.sendMassUpdateEventMailing(event);
        } catch (Exception e) {
            log.error("Failed to send mass update mailing: {}", e.getMessage(), e);
        }
    }
}