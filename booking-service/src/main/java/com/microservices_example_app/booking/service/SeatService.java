package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Seat;
import com.microservices_example_app.booking.model.Venue;
import com.microservices_example_app.booking.repository.SeatRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import com.microservices_example_app.booking.specification.SeatSpecification;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class SeatService {

    private final SeatRepository seatRepository;
    private final VenueRepository venueRepository;

    @Transactional
    public SeatResponseDto create(SeatCreateRequestDto requestDto) {
        Venue venue = venueRepository.findById(requestDto.getVenueId())
                .orElseThrow(() -> new NotFoundException("Venue not found"));

        Seat seat = Seat.builder()
                .sector(requestDto.getSector())
                .row(requestDto.getRow())
                .number(requestDto.getNumber())
                .venue(venue)
                .build();

        return toResponseDto(seatRepository.save(seat));
    }

    @Transactional
    public SeatResponseDto getById(Integer id) {
        Seat seat = seatRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Seat not found"));
        return toResponseDto(seat);
    }

    @Transactional
    public List<SeatResponseDto> searchByFilter(SeatSearchRequestDto filter, int page, int size) {
        if (page < 1) {
            throw new IllegalArgumentException("Page must be >= 1");
        }
        if (size < 1) {
            throw new IllegalArgumentException("Size must be >= 1");
        }

        Specification<Seat> spec = Specification.where((Specification<Seat>) null);

        if (filter.getVenueId() != null) {
            spec = spec.and(SeatSpecification.hasVenueId(filter.getVenueId()));
        }

        if (filter.getSector() != null && !filter.getSector().isBlank()) {
            spec = spec.and(SeatSpecification.hasSector(filter.getSector()));
        }

        if (filter.getRow() != null && !filter.getRow().isBlank()) {
            spec = spec.and(SeatSpecification.hasRow(filter.getRow()));
        }

        if (filter.getNumber() != null && !filter.getNumber().isBlank()) {
            spec = spec.and(SeatSpecification.hasNumber(filter.getNumber()));
        }

        Pageable pageable = PageRequest.of(page - 1, size);

        return seatRepository.findAll(spec, pageable)
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Transactional
    public void deleteById(Integer id) {
        if (id == null || id < 1) {
            throw new IllegalArgumentException("Seat id must be positive");
        }

        if (!seatRepository.existsById(id)) {
            throw new NotFoundException("Seat not found");
        }

        seatRepository.deleteById(id);
    }
    @Transactional
    public long deleteByFilter(SeatDeleteRequestDto requestDto) {
        Specification<Seat> spec = Specification
                .where(SeatSpecification.hasVenueId(requestDto.getVenueId()))
                .and(SeatSpecification.hasSector(requestDto.getSector()))
                .and(SeatSpecification.hasRow(requestDto.getRow()))
                .and(SeatSpecification.hasNumber(requestDto.getNumber()));

        List<Seat> seats = seatRepository.findAll(spec);
        long count = seats.size();
        seatRepository.deleteAll(seats);
        return count;
    }

    @Transactional
    public SeatResponseDto updateSeatById(SeatUpdateRequestDto request) {
        if (request.getId() == null || request.getId() < 1) {
            throw new IllegalArgumentException("Seat id must be positive");
        }

        Seat seat = seatRepository.findById(request.getId())
                .orElseThrow(() -> new NotFoundException("No seat with id=" + request.getId()));

        var builder = Seat.builder().id(seat.getId());

        if (request.getSector() != null && !request.getSector().isBlank()) {
            builder.sector(request.getSector());
        } else {
            builder.sector(seat.getSector());
        }

        if (request.getRow() != null && !request.getRow().isBlank()) {
            builder.row(request.getRow());
        } else {
            builder.row(seat.getRow());
        }

        if (request.getNumber() != null && !request.getNumber().isBlank()) {
            builder.number(request.getNumber());
        } else {
            builder.number(seat.getNumber());
        }

        if (request.getVenueId() != null) {
            Venue venue = venueRepository.findById(request.getVenueId())
                    .orElseThrow(() -> new NotFoundException("Venue not found: " + request.getVenueId()));
            builder.venue(venue);
        } else {
            builder.venue(seat.getVenue());
        }

        Seat saved = seatRepository.save(builder.build());
        return toResponseDto(saved);
    }
    private SeatResponseDto toResponseDto(Seat seat) {
        return SeatResponseDto.builder()
                .id(seat.getId())
                .sector(seat.getSector())
                .row(seat.getRow())
                .number(seat.getNumber())
                .venueId(seat.getVenue().getId())
                .venuePlace(seat.getVenue().getPlace())
                .build();
    }
}