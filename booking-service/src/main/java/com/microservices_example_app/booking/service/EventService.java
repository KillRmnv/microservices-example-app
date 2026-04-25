package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.Venue;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import com.microservices_example_app.booking.specification.EventSpecification;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class EventService {

    private final EventRepository eventRepository;
    private final VenueRepository venueRepository;

    @Transactional
    public EventResponseDto create(EventCreateRequestDto requestDto) {
        Venue venue = venueRepository.findById(requestDto.getVenueId())
                .orElseThrow(() -> new NotFoundException("Venue not found"));

        Event event = Event.builder()
                .title(requestDto.getTitle())
                .startsAt(requestDto.getStartsAt())
                .endsAt(requestDto.getEndsAt())
                .venue(venue)
                .admissionMode(requestDto.getAdmissionMode())
                .build();

        return toResponseDto(eventRepository.save(event));
    }

    @Transactional
    public EventResponseDto getById(Integer id) {
        Event event = eventRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Event not found"));
        return toResponseDto(event);
    }

    @Transactional
    public List<EventResponseDto> getAll() {
        return eventRepository.findAll()
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Transactional
    public List<EventResponseDto> searchByFilter(EventSearchRequestDto filter, int page, int size) {
        if (page < 1) {
            throw new IllegalArgumentException("Page must be >= 1");
        }
        if (size < 1) {
            throw new IllegalArgumentException("Size must be >= 1");
        }

        Specification<Event> spec = Specification.where((Specification<Event>) null);

        if (filter.getTitle() != null && !filter.getTitle().isBlank()) {
            spec = spec.and(EventSpecification.hasTitle(filter.getTitle()));
        }

        if (filter.getVenueId() != null) {
            spec = spec.and(EventSpecification.hasVenueId(filter.getVenueId()));
        }

        if (filter.getAdmissionMode() != null) {
            spec = spec.and(EventSpecification.hasAdmissionMode(filter.getAdmissionMode()));
        }

        if (filter.getStartsFrom() != null) {
            spec = spec.and(EventSpecification.startsAfter(filter.getStartsFrom()));
        }

        if (filter.getStartsTo() != null) {
            spec = spec.and(EventSpecification.startsBefore(filter.getStartsTo()));
        }

        Pageable pageable = PageRequest.of(page - 1, size);

        return eventRepository.findAll(spec, pageable)
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Transactional
    public void deleteById(Integer id) {
        if (id == null || id < 1) {
            throw new IllegalArgumentException("Event id must be positive");
        }

        if (!eventRepository.existsById(id)) {
            throw new RuntimeException("Event not found");
        }

        eventRepository.deleteById(id);
    }
    @Transactional
    public long deleteByFilter(EventDeleteRequestDto requestDto) {
        Specification<Event> spec = Specification
                .where(EventSpecification.hasTitle(requestDto.getTitle()))
                .and(EventSpecification.hasVenueId(requestDto.getVenueId()))
                .and(EventSpecification.hasAdmissionMode(requestDto.getAdmissionMode()))
                .and(EventSpecification.startsAfter(requestDto.getStartsAt()))
                .and(EventSpecification.startsBefore(requestDto.getStartsAt()));

        List<Event> events = eventRepository.findAll(spec);
        long count = events.size();
        eventRepository.deleteAll(events);
        return count;
    }



    @Transactional
    public EventResponseDto updateEventById(EventUpdateRequestDto request) {
        if (request.getId() == null || request.getId() < 1) {
            throw new IllegalArgumentException("Event id must be positive");
        }

        Event event = eventRepository.findById(request.getId())
                .orElseThrow(() -> new NotFoundException("No event with id=" + request.getId()));

        var builder = Event.builder().id(event.getId());

        if (request.getTitle() != null && !request.getTitle().isBlank()) {
            builder.title(request.getTitle());
        } else {
            builder.title(event.getTitle());
        }

        if (request.getStartsAt() != null) {
            builder.startsAt(request.getStartsAt());
        } else {
            builder.startsAt(event.getStartsAt());
        }

        if (request.getEndsAt() != null) {
            builder.endsAt(request.getEndsAt());
        } else {
            builder.endsAt(event.getEndsAt());
        }

        if (request.getVenueId() != null) {
            Venue venue = venueRepository.findById(request.getVenueId())
                    .orElseThrow(() -> new NotFoundException("Venue not found: " + request.getVenueId()));
            builder.venue(venue);
        } else {
            builder.venue(event.getVenue());
        }

        if (request.getAdmissionMode() != null) {
            builder.admissionMode(request.getAdmissionMode());
        } else {
            builder.admissionMode(event.getAdmissionMode());
        }

        Event saved = eventRepository.save(builder.build());
        return toResponseDto(saved);
    }
    private EventResponseDto toResponseDto(Event event) {
        return EventResponseDto.builder()
                .id(event.getId())
                .title(event.getTitle())
                .startsAt(event.getStartsAt())
                .endsAt(event.getEndsAt())
                .venueId(event.getVenue().getId())
                .venuePlace(event.getVenue().getPlace())
                .admissionMode(event.getAdmissionMode())
                .build();
    }
}