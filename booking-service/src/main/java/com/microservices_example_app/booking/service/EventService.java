package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.event.DeleteEventEvent;
import com.microservices_example_app.booking.event.UpdateEventEvent;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.Ticket;
import com.microservices_example_app.booking.model.Venue;
import com.microservices_example_app.booking.producers.BookingCatalogProducer;
import com.microservices_example_app.booking.producers.NotificationKafkaUserProducer;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.TicketRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import com.microservices_example_app.booking.repository.ZoneAvailabilityProjection;
import com.microservices_example_app.booking.specification.EventSpecification;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.Caching;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.CachePut;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;

import java.util.Comparator;
import java.util.List;
import java.util.Objects;

@Service
@RequiredArgsConstructor
@Slf4j
public class EventService {

    /** Below this many active seats an event is reported as few_left. */
    private static final int FEW_LEFT_THRESHOLD = 10;
    /** Upper bound for the requested party size. */
    private static final int MAX_PARTY = 999;

    private final EventRepository eventRepository;
    private final VenueRepository venueRepository;
    private final NotificationKafkaUserProducer kafkaUserProducer;
    private final BookingCatalogProducer catalogProducer;
    private final TicketRepository ticketRepository;
    @PersistenceContext
    private EntityManager entityManager;
    @Value("${spring.application.name}")
    private String serviceName;

    @CacheEvict(cacheNames = "eventSearch", allEntries = true)
    @Transactional
    public EventResponseDto create(EventCreateRequestDto requestDto) {
        log.info("Creating event: {}", requestDto.getTitle());

        Venue venue = venueRepository.findById(requestDto.getVenueId()).orElseThrow(() -> new NotFoundException("Venue not found"));

        Event event = Event.builder().title(requestDto.getTitle()).
                startsAt(requestDto.getStartsAt()).
                endsAt(requestDto.getEndsAt()).
                venue(venue).
                category(requestDto.getCategory() == null || requestDto.getCategory().isBlank()
                        ? "other" : requestDto.getCategory()).
                admissionMode(requestDto.getAdmissionMode()).build();

        Event saved = eventRepository.save(event);
        catalogProducer.sendUpsert(saved);
        log.info("Created event with id: {}", saved.getId());
        return toResponseDto(saved);
    }

    @Cacheable(cacheNames = "eventsById", key = "#id")
    @Transactional
    public EventResponseDto getById(Long id) {
        log.info("Fetching event with id: {}", id);

        Event event = eventRepository.findById(id).orElseThrow(() -> new NotFoundException("Event not found"));

        return toResponseDto(event);
    }

    @Transactional
    public List<EventResponseDto> getAll() {
        return eventRepository.findAll().stream().map(this::toResponseDto).toList();
    }

    @Cacheable(cacheNames = "eventSearch", key =
            "{#filter.title, #filter.venueId, #filter.admissionMode, #filter.startsFrom, #filter.startsTo, #page, #size}")
    @Transactional
    public List<EventResponseDto> searchByFilter(EventSearchRequestDto filter, int page, int size) {
        if (page < 1) {
            throw new IllegalArgumentException("Page must be >= 1");
        }
        if (size < 1) {
            throw new IllegalArgumentException("Size must be >= 1");
        }

        Specification<Event> spec = Specification.
                where(EventSpecification.hasTitle(filter.getTitle())).
                and(EventSpecification.hasVenueId(filter.getVenueId())).
                and(EventSpecification.hasCategory(filter.getCategory())).
                and(EventSpecification.hasAdmissionMode(filter.getAdmissionMode())).
                and(EventSpecification.startsAfter(filter.getStartsFrom())).
                and(EventSpecification.startsBefore(filter.getStartsTo()));


        Pageable pageable = PageRequest.of(page - 1, size);
        log.debug("Search by filter: title={}, venueId={}, admissionMode={}, startsFrom={}, startsTo={}, page={}, size={}",
                filter.getTitle(), filter.getVenueId(), filter.getAdmissionMode(), filter.getStartsFrom(), filter.getStartsTo(), page, size);

        return eventRepository.findAll(spec, pageable).stream().map(this::toResponseDto).toList();
    }

    @Caching(evict = {@CacheEvict(cacheNames = "eventsById", key = "#id"), @CacheEvict(cacheNames = "eventSearch", allEntries = true)})
    @Transactional
    public void deleteById(Long id) {
        if (id == null || id < 1) {
            throw new IllegalArgumentException("Event id must be positive");
        }
        Event event = eventRepository.findById(id).orElseThrow(() -> {
            throw new NotFoundException("Event not found");
        });

        DeleteEventEvent deleteEventEvent = new DeleteEventEvent(List.of(event.getTitle()), serviceName,
                ticketRepository.findByEventId(event.getId()).stream().
                map(Ticket::getUserId).toList());
        catalogProducer.sendDeleted(event);
        entityManager.clear();
        log.info("Deleting event with id: {}", id);
        eventRepository.deleteById(id);
        eventRepository.flush();

        kafkaUserProducer.sendDeleteEventEvent(deleteEventEvent);
    }

    @Caching(evict = {@CacheEvict(cacheNames = "eventsById", allEntries = true),
            @CacheEvict(cacheNames = "eventSearch", allEntries = true)})
    @Transactional
    public long deleteByFilter(EventDeleteRequestDto requestDto) {
        Specification<Event> spec = Specification.
                where(EventSpecification.hasTitle(requestDto.getTitle())).
                and(EventSpecification.hasVenueId(requestDto.getVenueId())).
                and(EventSpecification.hasAdmissionMode(requestDto.getAdmissionMode())).
                and(EventSpecification.startsAfter(requestDto.getStartsAt())).
                and(EventSpecification.startsBefore(requestDto.getEndsAt()));

        log.debug("Delete by filter: title={}, venueId={}, admissionMode={}, startsAt={}", requestDto.getTitle(),
                requestDto.getVenueId(), requestDto.getAdmissionMode(), requestDto.getStartsAt());

        List<Event> events = eventRepository.findAll(spec);
        long count = events.size();

        log.info("Delete by filter amount: {}", count);
        List<String> titles = events.stream().map(Event::getTitle).toList();
        List<Long> userIds = ticketRepository.findByEventIdIn(events.stream().map(Event::getId).toList())
                .stream()
                .map(Ticket::getUserId)
                .filter(Objects::nonNull)
                .distinct()
                .toList();
        DeleteEventEvent deleteEventEvent = new DeleteEventEvent(titles, serviceName, userIds);
        events.forEach(catalogProducer::sendDeleted);
        entityManager.clear();
        eventRepository.deleteAll(events);
        eventRepository.flush();
        kafkaUserProducer.sendDeleteEventEvent(deleteEventEvent);
        return count;
    }

    @Caching(put = {@CachePut(cacheNames = "eventsById", key = "#result.id")},
            evict = {@CacheEvict(cacheNames = "eventSearch", allEntries = true)})
    @Transactional
    public EventResponseDto updateEventById(EventUpdateRequestDto request) {
        if (request.getId() == null || request.getId() < 1) {
            throw new IllegalArgumentException("Event id must be positive");
        }

        Event event = eventRepository.findById(request.getId()).orElseThrow(() -> new NotFoundException("No event with id=" + request.getId()));

        var builder = Event.builder().id(event.getId());
        StringBuilder stringBuilder = new StringBuilder("Actual info:\n");
        if (request.getTitle() != null && !request.getTitle().isBlank()) {
            builder.title(request.getTitle());
            stringBuilder.append("Title:").append(request.getTitle()).append("\n");
        } else {
            builder.title(event.getTitle());
            stringBuilder.append("Title:").append(event.getTitle()).append("\n");
        }

        if (request.getStartsAt() != null) {
            builder.startsAt(request.getStartsAt());
            stringBuilder.append("Date:").append(request.getStartsAt()).append("\n");
        } else {
            builder.startsAt(event.getStartsAt());
            stringBuilder.append("Date:").append(event.getStartsAt()).append("\n");
        }

        if (request.getEndsAt() != null) {
            builder.endsAt(request.getEndsAt());
            stringBuilder.append("Ends:").append(request.getEndsAt()).append("\n");
        } else {
            builder.endsAt(event.getEndsAt());
            stringBuilder.append("Ends:").append(event.getEndsAt()).append("\n");
        }

        if (request.getVenueId() != null) {
            Venue venue = venueRepository.findById(request.getVenueId()).orElseThrow(
                    () -> new NotFoundException("Venue not found: " + request.getVenueId()));
            builder.venue(venue);
            stringBuilder.append("Venue:").append(venue.getPlace()).append("\n");
        } else {
            builder.venue(event.getVenue());
            stringBuilder.append("Venue:").append(event.getVenue().getPlace()).append("\n");
        }

        if (request.getCategory() != null && !request.getCategory().isBlank()) {
            builder.category(request.getCategory());
            stringBuilder.append("Category:").append(request.getCategory()).append("\n");
        } else {
            builder.category(event.getCategory());
            stringBuilder.append("Category:").append(event.getCategory()).append("\n");
        }

        if (request.getAdmissionMode() != null) {
            builder.admissionMode(request.getAdmissionMode());
            stringBuilder.append("Admission:").append(request.getAdmissionMode()).append("\n");
        } else {
            builder.admissionMode(event.getAdmissionMode());
            stringBuilder.append("Admission:").append(event.getAdmissionMode()).append("\n");
        }

        log.info("Updating event with id: {}", event.getId());
        Event toSave = builder.build();
        UpdateEventEvent updateEventEvent = new UpdateEventEvent(
                List.of(toSave.getTitle()), serviceName, stringBuilder.toString(),
                ticketRepository.findByEventId(toSave.getId()).stream().map(Ticket::getUserId).toList());
        toSave = eventRepository.save(toSave);

        kafkaUserProducer.sendUpdateEventEvent(updateEventEvent);
        catalogProducer.sendUpsert(toSave);

        return toResponseDto(toSave);
    }

    /**
     * Exact, party-aware availability for a single event.
     *
     * <p>Uses aggregate SQL only, so no ticket entities are loaded. {@code party}
     * is clamped to {@code 0..999}; {@code 0} means "any party size". A missing
     * event raises {@link NotFoundException} (HTTP 404) — consumers treat that
     * as {@code unknown} rather than a status value.</p>
     */
    @org.springframework.transaction.annotation.Transactional(readOnly = true)
    public EventAvailabilityResponseDto availability(Long eventId, int party) {
        int requestedParty = Math.max(0, Math.min(party, MAX_PARTY));
        log.debug("Fetching availability for event {} and party {}", eventId, requestedParty);

        Event event = eventRepository.findById(eventId)
                .orElseThrow(() -> new NotFoundException("Event not found"));

        List<ZoneAvailabilityDto> zones = ticketRepository.aggregateActiveByZone(eventId).stream()
                .map(this::toZoneAvailabilityDto)
                .sorted(Comparator.comparing(ZoneAvailabilityDto::getMinPrice,
                                Comparator.nullsLast(Comparator.naturalOrder()))
                        .thenComparing(ZoneAvailabilityDto::getZone))
                .toList();

        long totalSeats = zones.stream().mapToLong(ZoneAvailabilityDto::getSeatsLeft).sum();
        Integer capacity = event.getVenue() != null ? event.getVenue().getCapacity() : null;

        return EventAvailabilityResponseDto.builder().
                eventId(event.getId()).
                status(resolveAvailabilityStatus(zones, totalSeats, requestedParty)).
                capacity(capacity).
                zones(zones).
                build();
    }

    private ZoneAvailabilityDto toZoneAvailabilityDto(ZoneAvailabilityProjection projection) {
        return ZoneAvailabilityDto.builder().
                zone(projection.getZone()).
                seatsLeft(projection.getSeatsLeft() != null ? projection.getSeatsLeft() : 0L).
                minPrice(projection.getMinPrice()).
                build();
    }

    private AvailabilityStatus resolveAvailabilityStatus(List<ZoneAvailabilityDto> zones, long totalSeats, int party) {
        if (totalSeats == 0) {
            return AvailabilityStatus.SOLD_OUT;
        }
        if (party >= 1 && zones.stream().noneMatch(zone -> zone.getSeatsLeft() >= party)) {
            return AvailabilityStatus.INSUFFICIENT;
        }
        if (totalSeats < FEW_LEFT_THRESHOLD) {
            return AvailabilityStatus.FEW_LEFT;
        }
        long perZoneBar = Math.max(FEW_LEFT_THRESHOLD, (long) party * 3);
        if (zones.stream().allMatch(zone -> zone.getSeatsLeft() < perZoneBar)) {
            return AvailabilityStatus.FEW_LEFT;
        }
        return AvailabilityStatus.AVAILABLE;
    }

    private EventResponseDto toResponseDto(Event event) {
        return EventResponseDto.builder().
                id(event.getId()).
                title(event.getTitle()).
                startsAt(event.getStartsAt()).
                endsAt(event.getEndsAt()).
                venueId(event.getVenue().getId()).
                venuePlace(event.getVenue().getPlace()).
                venueCapacity(event.getVenue().getCapacity()).
                category(event.getCategory()).
                admissionMode(event.getAdmissionMode()).
                build();
    }
}