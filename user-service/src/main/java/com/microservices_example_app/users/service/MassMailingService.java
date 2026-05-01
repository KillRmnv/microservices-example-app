package com.microservices_example_app.users.service;

import com.microservices_example_app.users.event.*;
import com.microservices_example_app.users.producers.NotificationKafkaMassMailingProducer;
import com.microservices_example_app.users.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class MassMailingService {

    private final UserRepository userRepository;
    private final NotificationKafkaMassMailingProducer massMailingProducer;

    @Value("${spring.application.name}")
    private String serviceName;

    public void processDeleteEventMailing(DeleteEventEvent event) {
        log.info("Processing DeleteEventEvent: {} events, {} userIds",
                event.getEvents().size(), event.getUserIds().size());

        List<UserNotificationDto> users = userRepository.findAllById(event.getUserIds())
                .stream()
                .map(u -> new UserNotificationDto(u.getEmail(), u.getUsername()))
                .toList();

        if (users.isEmpty()) {
            log.warn("No users found for userIds={}", event.getUserIds());
            return;
        }

        MassDeleteEventMailingEvent mailingEvent = new MassDeleteEventMailingEvent(
                event.getEvents(),
                users,
                event.getSourceService()
        );

        massMailingProducer.sendMassDeleteEventMailing(mailingEvent);
        log.info("MassDeleteEventMailingEvent sent: {} users notified", users.size());
    }

    public void processUpdateEventMailing(UpdateEventEvent event) {
        log.info("Processing UpdateEventEvent: {} events, {} userIds",
                event.getEvents().size(), event.getUserIds().size());

        List<UserNotificationDto> users = userRepository.findAllById(event.getUserIds())
                .stream()
                .map(u -> new UserNotificationDto(u.getEmail(), u.getUsername()))
                .toList();

        if (users.isEmpty()) {
            log.warn("No users found for userIds={}", event.getUserIds());
            return;
        }

        MassUpdateEventMailingEvent mailingEvent = new MassUpdateEventMailingEvent(
                event.getEvents(),
                event.getChangesDescription(),
                users,
                event.getSourceService()
        );

        massMailingProducer.sendMassUpdateEventMailing(mailingEvent);
        log.info("MassUpdateEventMailingEvent sent: {} users notified", users.size());
    }
}