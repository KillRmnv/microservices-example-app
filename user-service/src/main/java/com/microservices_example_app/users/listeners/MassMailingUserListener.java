package com.microservices_example_app.users.listeners;

import com.microservices_example_app.users.event.DeleteEventEvent;
import com.microservices_example_app.users.event.UpdateEventEvent;
import com.microservices_example_app.users.service.MassMailingService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
@Slf4j
public class MassMailingUserListener {

    private final MassMailingService massMailingService;

    @KafkaListener(
            topics = "${topic.mass-mailing}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "deleteEventEventKafkaListenerContainerFactory"
    )
    public void handleDeleteEventEvent(DeleteEventEvent event) {
        log.info("Received DeleteEventEvent from service={}, events={}",
                event.getSourceService(), event.getEvents());
        massMailingService.processDeleteEventMailing(event);
    }

    @KafkaListener(
            topics = "${topic.mass-mailing}",
            groupId = "${spring.kafka.consumer.group-id}",
            containerFactory = "updateEventEventKafkaListenerContainerFactory"
    )
    public void handleUpdateEventEvent(UpdateEventEvent event) {
        log.info("Received UpdateEventEvent from service={}, events={}",
                event.getSourceService(), event.getEvents());
        massMailingService.processUpdateEventMailing(event);
    }
}