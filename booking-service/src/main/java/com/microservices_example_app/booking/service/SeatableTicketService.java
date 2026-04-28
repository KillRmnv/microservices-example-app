package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.event.SuccessfulBookingEvent;
import com.microservices_example_app.booking.event.SuccessfulTicketRefundEvent;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Event;
import com.microservices_example_app.booking.model.Seat;
import com.microservices_example_app.booking.model.SeatableTicket;
import com.microservices_example_app.booking.producers.NotificationKafkaBookingProducer;
import com.microservices_example_app.booking.repository.EventRepository;
import com.microservices_example_app.booking.repository.SeatRepository;
import com.microservices_example_app.booking.repository.SeatableTicketRepository;
import com.microservices_example_app.booking.specification.SeatableTicketSpecification;
import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class SeatableTicketService {

    private final SeatableTicketRepository seatableTicketRepository;
    private final EventRepository eventRepository;
    private final SeatRepository seatRepository;
    private final NotificationKafkaBookingProducer notificationKafkaBookingProducer;
    private final JwtRequestUserExtractor jwtRequestUserExtractor;

    @Value("${spring.application.name}")
    private String serviceName;

    @Transactional
    public SeatableTicketResponseDto create(SeatableTicketCreateRequestDto requestDto) {
        log.info("Creating seatable ticket for event id: {}", requestDto.getEventId());

        Event event = eventRepository.findById(requestDto.getEventId())
                .orElseThrow(() -> new NotFoundException("Event not found"));

        Seat seat = seatRepository.findById(requestDto.getSeatId())
                .orElseThrow(() -> new NotFoundException("Seat not found"));

        Integer currentUserId = jwtRequestUserExtractor.extractUserId();
        String email = jwtRequestUserExtractor.extractEmail();
        String username = jwtRequestUserExtractor.extractUsername();

        SeatableTicket seatableTicket = SeatableTicket.builder()
                .event(event)
                .seat(seat)
                .zone(requestDto.getZone())
                .price(requestDto.getPrice())
                .active(Boolean.TRUE.equals(requestDto.getActive()))
                .userId(currentUserId)
                .build();

        SeatableTicket saved = seatableTicketRepository.save(seatableTicket);

        SuccessfulBookingEvent bookingEvent = new SuccessfulBookingEvent(
                email,
                username,
                saved.getEvent().getTitle(),
                serviceName
        );

        notificationKafkaBookingProducer.sendSuccessfulBookingEvent(bookingEvent);
        log.info("Successful seatable booking event sent for ticket id={}, email={}", saved.getId(), email);

        return toResponseDto(saved);
    }

    @Transactional
    public SeatableTicketResponseDto getById(Integer id) {
        log.info("Fetching seatable ticket with id: {}", id);

        SeatableTicket ticket = seatableTicketRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Seatable ticket not found"));

        return toResponseDto(ticket);
    }

    @Transactional
    public void deleteById(Integer id) {
        if (id == null || id < 1) {
            throw new IllegalArgumentException("SeatableTicket id must be positive");
        }

        SeatableTicket ticket = seatableTicketRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Seatable ticket not found"));

        Integer currentUserId = jwtRequestUserExtractor.extractUserId();
        String email = jwtRequestUserExtractor.extractEmail();
        String username = jwtRequestUserExtractor.extractUsername();

        if (!ticket.getUserId().equals(currentUserId)) {
            log.warn("User id={} attempted to delete foreign seatable ticket id={}", currentUserId, id);
            throw new IllegalArgumentException("You can delete only your own seatable ticket");
        }

        log.info("Deleting seatable ticket with id={}, userId={}", id, currentUserId);
        seatableTicketRepository.delete(ticket);

        SuccessfulTicketRefundEvent refundEvent = new SuccessfulTicketRefundEvent(
                email,
                username,
                ticket.getEvent().getTitle(),
                serviceName
        );

        notificationKafkaBookingProducer.sendSuccessfulTicketRefundEvent(refundEvent);
        log.info("Successful seatable refund event sent for ticket id={}, email={}", id, email);
    }

    @Transactional
    public long deleteByFilter(SeatableTicketDeleteRequestDto requestDto) {
        Integer currentUserId = jwtRequestUserExtractor.extractUserId();

        Specification<SeatableTicket> spec = Specification
                .where(SeatableTicketSpecification.hasEventId(requestDto.getEventId()))
                .and(SeatableTicketSpecification.hasSeatId(requestDto.getSeatId()))
                .and(SeatableTicketSpecification.hasUserId(currentUserId))
                .and(SeatableTicketSpecification.hasZone(requestDto.getZone()))
                .and(SeatableTicketSpecification.hasActive(requestDto.getActive()))
                .and(SeatableTicketSpecification.hasPriceGreaterThanOrEqual(requestDto.getMinPrice()))
                .and(SeatableTicketSpecification.hasPriceLessThanOrEqual(requestDto.getMaxPrice()))
                .and(SeatableTicketSpecification.hasSector(requestDto.getSector()))
                .and(SeatableTicketSpecification.hasRow(requestDto.getRow()))
                .and(SeatableTicketSpecification.hasNumber(requestDto.getNumber()));

        log.debug("Delete by filter for userId={}: {}", currentUserId, spec);
        List<SeatableTicket> tickets = seatableTicketRepository.findAll(spec);
        long count = tickets.size();
        log.info("Delete by filter amount for userId={}: {}", currentUserId, count);
        seatableTicketRepository.deleteAll(tickets);
        return count;
    }

    @Transactional
    public List<SeatableTicketResponseDto> searchByFilter(SeatableTicketSearchRequestDto filter, int page, int size) {
        if (page < 1) {
            throw new IllegalArgumentException("Page must be >= 1");
        }
        if (size < 1) {
            throw new IllegalArgumentException("Size must be >= 1");
        }

        Integer currentUserId = jwtRequestUserExtractor.extractUserId();

        Specification<SeatableTicket> spec = Specification
                .where(SeatableTicketSpecification.hasEventId(filter.getEventId()))
                .and(SeatableTicketSpecification.hasSeatId(filter.getSeatId()))
                .and(SeatableTicketSpecification.hasUserId(currentUserId))
                .and(SeatableTicketSpecification.hasZone(filter.getZone()))
                .and(SeatableTicketSpecification.hasActive(filter.getActive()))
                .and(SeatableTicketSpecification.hasPriceGreaterThanOrEqual(filter.getMinPrice()))
                .and(SeatableTicketSpecification.hasPriceLessThanOrEqual(filter.getMaxPrice()))
                .and(SeatableTicketSpecification.hasSector(filter.getSector()))
                .and(SeatableTicketSpecification.hasRow(filter.getRow()))
                .and(SeatableTicketSpecification.hasNumber(filter.getNumber()));

        Pageable pageable = PageRequest.of(page - 1, size);
        log.debug("Search by filter for userId={}: {}", currentUserId, spec);

        return seatableTicketRepository.findAll(spec, pageable)
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Transactional
    public SeatableTicketResponseDto updateSeatableTicketById(SeatableTicketUpdateRequestDto request) {
        if (request.getId() == null || request.getId() < 1) {
            throw new IllegalArgumentException("SeatableTicket id must be positive");
        }

        SeatableTicket ticket = seatableTicketRepository.findById(request.getId())
                .orElseThrow(() -> new NotFoundException("No seatable ticket with id=" + request.getId()));

        var builder = SeatableTicket.builder().id(ticket.getId());

        if (request.getEventId() != null) {
            Event event = eventRepository.findById(request.getEventId())
                    .orElseThrow(() -> new NotFoundException("Event not found: " + request.getEventId()));
            builder.event(event);
        } else {
            builder.event(ticket.getEvent());
        }

        if (request.getSeatId() != null) {
            Seat seat = seatRepository.findById(request.getSeatId())
                    .orElseThrow(() -> new IllegalArgumentException("Seat not found: " + request.getSeatId()));
            builder.seat(seat);
        } else {
            builder.seat(ticket.getSeat());
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

        builder.userId(ticket.getUserId());

        log.info("Update seatable ticket with id: {}", ticket.getId());
        SeatableTicket saved = seatableTicketRepository.save(builder.build());
        return toResponseDto(saved);
    }

    private SeatableTicketResponseDto toResponseDto(SeatableTicket ticket) {
        return SeatableTicketResponseDto.builder()
                .id(ticket.getId())
                .eventId(ticket.getEvent().getId())
                .eventTitle(ticket.getEvent().getTitle())
                .seatId(ticket.getSeat().getId())
                .sector(ticket.getSeat().getSector())
                .row(ticket.getSeat().getRow())
                .number(ticket.getSeat().getNumber())
                .zone(ticket.getZone())
                .price(ticket.getPrice())
                .active(ticket.isActive())
                .userId(ticket.getUserId())
                .build();
    }
}