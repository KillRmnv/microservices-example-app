package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.Ticket;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.TicketRepository;
import com.microservices_example_app.booking.specification.TicketSpecification;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class TicketService {

    private final TicketRepository ticketRepository;
    private final EventRepository eventRepository;

    @Transactional
    public TicketResponseDto create(TicketCreateRequestDto requestDto) {
        Event event = eventRepository.findById(requestDto.getEventId())
                .orElseThrow(() -> new NotFoundException("Event not found"));

        Ticket ticket = Ticket.builder()
                .event(event)
                .zone(requestDto.getZone())
                .price(requestDto.getPrice())
                .active(Boolean.TRUE.equals(requestDto.getActive()))
                .userId(requestDto.getUserId())
                .build();

        return toResponseDto(ticketRepository.save(ticket));
    }

    @Transactional
    public TicketResponseDto getById(Integer id) {
        Ticket ticket = ticketRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Ticket not found"));
        return toResponseDto(ticket);
    }

    @Transactional
    public List<TicketResponseDto> searchByFilter(TicketSearchRequestDto filter, int page, int size) {
        if (page < 1) {
            throw new IllegalArgumentException("Page must be >= 1");
        }
        if (size < 1) {
            throw new IllegalArgumentException("Size must be >= 1");
        }

        Specification<Ticket> spec = Specification.where((Specification<Ticket>) null);

        if (filter.getEventId() != null) {
            spec = spec.and(TicketSpecification.hasEventId(filter.getEventId()));
        }

        if (filter.getUserId() != null) {
            spec = spec.and(TicketSpecification.hasUserId(filter.getUserId()));
        }

        if (filter.getZone() != null) {
            spec = spec.and(TicketSpecification.hasZone(filter.getZone()));
        }

        if (filter.getActive() != null) {
            spec = spec.and(TicketSpecification.hasActive(filter.getActive()));
        }

        if (filter.getMinPrice() != null) {
            spec = spec.and(TicketSpecification.hasPriceGreaterThanOrEqual(filter.getMinPrice()));
        }

        if (filter.getMaxPrice() != null) {
            spec = spec.and(TicketSpecification.hasPriceLessThanOrEqual(filter.getMaxPrice()));
        }

        Pageable pageable = PageRequest.of(page - 1, size);

        return ticketRepository.findAll(spec, pageable)
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Transactional
    public void deleteById(Integer id) {
        if (id == null || id < 1) {
            throw new IllegalArgumentException("Ticket id must be positive");
        }

        if (!ticketRepository.existsById(id)) {
            throw new NotFoundException("Ticket not found");
        }

        ticketRepository.deleteById(id);
    }
    @Transactional
    public long deleteByFilter(TicketDeleteRequestDto requestDto) {
        Specification<Ticket> spec = Specification
                .where(TicketSpecification.hasEventId(requestDto.getEventId()))
                .and(TicketSpecification.hasUserId(requestDto.getUserId()))
                .and(TicketSpecification.hasZone(requestDto.getZone()))
                .and(TicketSpecification.hasActive(requestDto.getActive()))
                .and(TicketSpecification.hasPriceGreaterThanOrEqual(requestDto.getMinPrice()))
                .and(TicketSpecification.hasPriceLessThanOrEqual(requestDto.getMaxPrice()));

        List<Ticket> tickets = ticketRepository.findAll(spec);
        long count = tickets.size();
        ticketRepository.deleteAll(tickets);
        return count;
    }


    @Transactional
    public TicketResponseDto updateTicketById(TicketUpdateRequestDto request) {
        if (request.getId() == null || request.getId() < 1) {
            throw new IllegalArgumentException("Ticket id must be positive");
        }

        Ticket ticket = ticketRepository.findById(request.getId())
                .orElseThrow(() -> new NotFoundException("No ticket with id=" + request.getId()));

        var builder = Ticket.builder().id(ticket.getId());

        if (request.getEventId() != null) {
            Event event = eventRepository.findById(request.getEventId())
                    .orElseThrow(() -> new NotFoundException("Event not found: " + request.getEventId()));
            builder.event(event);
        } else {
            builder.event(ticket.getEvent());
        }

        if (request.getZone() != null) {
            builder.zone(request.getZone());
        } else {
            builder.zone(ticket.getZone());
        }

        if (request.getPrice() != null) {
            builder.price(request.getPrice());
        } else {
            builder.price(ticket.getPrice());
        }

        if (request.getActive() != null) {
            builder.active(request.getActive());
        } else {
            builder.active(ticket.isActive());
        }

        if (request.getUserId() != null) {
            builder.userId(request.getUserId());
        } else {
            builder.userId(ticket.getUserId());
        }

        Ticket saved = ticketRepository.save(builder.build());
        return toResponseDto(saved);
    }
    private TicketResponseDto toResponseDto(Ticket ticket) {
        return TicketResponseDto.builder()
                .id(ticket.getId())
                .eventId(ticket.getEvent().getId())
                .eventTitle(ticket.getEvent().getTitle())
                .zone(ticket.getZone())
                .price(ticket.getPrice())
                .active(ticket.isActive())
                .userId(ticket.getUserId())
                .build();
    }
}