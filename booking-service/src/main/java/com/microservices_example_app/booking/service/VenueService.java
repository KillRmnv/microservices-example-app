package com.microservices_example_app.booking.service;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.exceptions.NotFoundException;
import com.microservices_example_app.booking.model.Town;
import com.microservices_example_app.booking.model.Venue;
import com.microservices_example_app.booking.repository.TownRepository;
import com.microservices_example_app.booking.repository.VenueRepository;
import com.microservices_example_app.booking.specification.VenueSpecification;
import jakarta.transaction.Transactional;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
public class VenueService {

    private final VenueRepository venueRepository;
    private final TownRepository townRepository;

    @Transactional
    public VenueResponseDto create(VenueCreateRequestDto requestDto) {
        Town town = townRepository.findById(requestDto.getTownId())
                .orElseThrow(() -> new NotFoundException("Town not found"));

        Venue venue = Venue.builder()
                .town(town)
                .place(requestDto.getPlace())
                .capacity(requestDto.getCapacity())
                .build();

        return toResponseDto(venueRepository.save(venue));
    }

    @Transactional
    public VenueResponseDto getById(Integer id) {
        Venue venue = venueRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Venue not found"));
        return toResponseDto(venue);
    }


    @Transactional
    public void deleteById(Integer id) {
        if (id == null || id < 1) {
            throw new IllegalArgumentException("Venue id must be positive");
        }

        if (!venueRepository.existsById(id)) {
            throw new NotFoundException("Venue not found");
        }

        venueRepository.deleteById(id);
    }
    @Transactional
    public long deleteByFilter(VenueDeleteRequestDto requestDto) {
        Specification<Venue> spec = Specification
                .where(VenueSpecification.hasTownId(requestDto.getTownId()))
                .and(VenueSpecification.hasPlace(requestDto.getPlace()))
                .and(VenueSpecification.hasCapacityGreaterThanOrEqual(requestDto.getMinCapacity()))
                .and(VenueSpecification.hasCapacityLessThanOrEqual(requestDto.getMaxCapacity()));

        List<Venue> venues = venueRepository.findAll(spec);
        long count = venues.size();
        venueRepository.deleteAll(venues);
        return count;
    }

    @Transactional
    public List<VenueResponseDto> searchByFilter(VenueSearchRequestDto filter, int page, int size) {
        if (page < 1) {
            throw new IllegalArgumentException("Page must be >= 1");
        }
        if (size < 1) {
            throw new IllegalArgumentException("Size must be >= 1");
        }

        Specification<Venue> spec = Specification.where((Specification<Venue>) null);

        if (filter.getTownId() != null) {
            spec = spec.and(VenueSpecification.hasTownId(filter.getTownId()));
        }

        if (filter.getPlace() != null && !filter.getPlace().isBlank()) {
            spec = spec.and(VenueSpecification.hasPlace(filter.getPlace()));
        }

        if (filter.getMinCapacity() != null) {
            spec = spec.and(VenueSpecification.hasCapacityGreaterThanOrEqual(filter.getMinCapacity()));
        }

        if (filter.getMaxCapacity() != null) {
            spec = spec.and(VenueSpecification.hasCapacityLessThanOrEqual(filter.getMaxCapacity()));
        }

        Pageable pageable = PageRequest.of(page - 1, size);

        return venueRepository.findAll(spec, pageable)
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Transactional
    public VenueResponseDto updateVenueById(VenueUpdateRequestDto request) {
        if (request.getId() == null || request.getId() < 1) {
            throw new IllegalArgumentException("Venue id must be positive");
        }

        Venue venue = venueRepository.findById(request.getId())
                .orElseThrow(() -> new NotFoundException("No venue with id=" + request.getId()));

        var builder = Venue.builder().id(venue.getId());

        if (request.getTownId() != null) {
            Town town = townRepository.findById(request.getTownId())
                    .orElseThrow(() -> new NotFoundException("Town not found: " + request.getTownId()));
            builder.town(town);
        } else {
            builder.town(venue.getTown());
        }

        if (request.getPlace() != null && !request.getPlace().isBlank()) {
            builder.place(request.getPlace());
        } else {
            builder.place(venue.getPlace());
        }

        if (request.getCapacity() != null) {
            builder.capacity(request.getCapacity());
        } else {
            builder.capacity(venue.getCapacity());
        }

        Venue saved = venueRepository.save(builder.build());
        return toResponseDto(saved);
    }
    private VenueResponseDto toResponseDto(Venue venue) {
        return VenueResponseDto.builder()
                .id(venue.getId())
                .townId(venue.getTown().getId())
                .townName(venue.getTown().getName())
                .place(venue.getPlace())
                .capacity(venue.getCapacity())
                .build();
    }
}