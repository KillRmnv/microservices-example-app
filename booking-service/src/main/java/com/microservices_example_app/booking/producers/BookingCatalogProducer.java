package com.microservices_example_app.booking.producers;

import com.microservices_example_app.booking.event.BookingCatalogEvent;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.utils.TransactionalEventPublisher;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import java.time.ZoneOffset;
import java.util.List;

/**
 * Publishes the searchable event catalog to Kafka.
 *
 * <p>Topic is compacted and keyed by event id, so every message is the full
 * current state of one event and the last write wins. Deletes are tombstones
 * ({@code deleted=true}) instead of absent records.</p>
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class BookingCatalogProducer {

    private final KafkaTemplate<String, BookingCatalogEvent> bookingCatalogKafkaTemplate;
    private final TransactionalEventPublisher transactionalEventPublisher;
    private final EventRepository eventRepository;

    @Value("${topic.booking.catalog:booking.catalog}")
    private String catalogTopic;

    @Value("${booking.catalog.publish-on-startup:true}")
    private boolean publishOnStartup;

    /** After commit: keeps the catalog in sync with the database. */
    public void sendUpsert(Event event) {
        publishAfterCommit(toCatalogEvent(event, false));
    }

    public void sendDeleted(Event event) {
        publishAfterCommit(toCatalogEvent(event, true));
    }

    /**
     * Replays the whole catalog once the context is ready. This is the
     * bootstrap path: no snapshot endpoint, a fresh consumer reads the
     * compacted topic from the beginning.
     */
    @EventListener(ApplicationReadyEvent.class)
    @Transactional
    public void republishOnStartup() {
        if (!publishOnStartup) {
            return;
        }
        List<Event> events = eventRepository.findAll();
        for (Event event : events) {
            bookingCatalogKafkaTemplate.send(
                    catalogTopic, String.valueOf(event.getId()),
                    toCatalogEvent(event, false));
        }
        log.info("Published {} catalog events to topic={} on startup",
                events.size(), catalogTopic);
    }

    private void publishAfterCommit(BookingCatalogEvent payload) {
        transactionalEventPublisher.sendAfterCommit(
                bookingCatalogKafkaTemplate, catalogTopic,
                String.valueOf(payload.getId()), payload);
    }

    private static BookingCatalogEvent toCatalogEvent(Event event, boolean deleted) {
        return BookingCatalogEvent.builder()
                .id(event.getId())
                .title(event.getTitle())
                .startsAt(isoUtc(event.getStartsAt()))
                .endsAt(isoUtc(event.getEndsAt()))
                .venueId(event.getVenue().getId())
                .venuePlace(event.getVenue().getPlace())
                .townId(event.getVenue().getTown().getId())
                .townName(event.getVenue().getTown().getName())
                .category(event.getCategory())
                .admissionMode(event.getAdmissionMode().name())
                .deleted(deleted)
                .build();
    }

    private static String isoUtc(java.time.LocalDateTime value) {
        return value == null ? null : value.toInstant(ZoneOffset.UTC).toString();
    }
}
