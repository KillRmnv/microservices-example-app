package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.event.DeleteEventEvent;
import com.microservices_example_app.booking.event.UpdateEventEvent;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.Ticket;
import com.microservices_example_app.booking.model.Venue;
import com.microservices_example_app.booking.producers.NotificationKafkaBookingProducer;
import com.microservices_example_app.booking.producers.NotificationKafkaUserProducer;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.TicketRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import com.microservices_example_app.booking.specification.EventSpecification;
import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
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

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class EventService {

    private final EventRepository eventRepository;
    private final VenueRepository venueRepository;
    private final NotificationKafkaUserProducer kafkaUserProducer;
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
                admissionMode(requestDto.getAdmissionMode()).build();

        Event saved = eventRepository.save(event);
        log.info("Created event with id: {}", saved.getId());
        return toResponseDto(saved);
    }

    @Cacheable(cacheNames = "eventsById", key = "#id")
    @Transactional
    public EventResponseDto getById(Integer id) {
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
    public void deleteById(Integer id) {
        if (id == null || id < 1) {
            throw new IllegalArgumentException("Event id must be positive");
        }
        Event event = eventRepository.findById(id).orElseThrow(() -> {
            throw new NotFoundException("Event not found");
        });

        DeleteEventEvent deleteEventEvent = new DeleteEventEvent(List.of(event.getTitle()), serviceName,
                ticketRepository.findByEventId(event.getId()).stream().
                map(Ticket::getUserId).toList());
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
                and(EventSpecification.startsBefore(requestDto.getStartsAt()));

        log.debug("Delete by filter: title={}, venueId={}, admissionMode={}, startsAt={}", requestDto.getTitle(),
                requestDto.getVenueId(), requestDto.getAdmissionMode(), requestDto.getStartsAt());

        List<Event> events = eventRepository.findAll(spec);
        long count = events.size();

        log.info("Delete by filter amount: {}", count);
        List<String> titles = new ArrayList<>();
        List<Integer> userIds = new ArrayList<>();
        for (var e : events) {
            titles.add(e.getTitle());
            userIds.addAll(ticketRepository.findByEventId(e.getId()).stream().map(Ticket::getUserId).toList());
        }
        DeleteEventEvent deleteEventEvent = new DeleteEventEvent(titles, serviceName, userIds);
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

        return toResponseDto(toSave);
    }

    private EventResponseDto toResponseDto(Event event) {
        return EventResponseDto.builder().
                id(event.getId()).
                title(event.getTitle()).
                startsAt(event.getStartsAt()).
                endsAt(event.getEndsAt()).
                venueId(event.getVenue().getId()).
                venuePlace(event.getVenue().getPlace()).
                admissionMode(event.getAdmissionMode()).
                build();
    }
}