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
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.Caching;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.CachePut;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class VenueService {

    private final VenueRepository venueRepository;
    private final TownRepository townRepository;

    @CacheEvict(cacheNames = "venueSearch", allEntries = true)
    @Transactional
    public VenueResponseDto create(VenueCreateRequestDto requestDto) {
        log.info("Creating venue: {}", requestDto.getPlace());

        Town town = townRepository.findById(requestDto.getTownId())
                .orElseThrow(() -> new NotFoundException("Town not found"));

        Venue venue = Venue.builder()
                .town(town)
                .place(requestDto.getPlace())
                .capacity(requestDto.getCapacity())
                .build();

        Venue saved = venueRepository.save(venue);
        log.info("Created venue with id: {}", saved.getId());
        return toResponseDto(saved);
    }

    @Cacheable(cacheNames = "venuesById", key = "#id")
    @Transactional
    public VenueResponseDto getById(Integer id) {
        log.info("Fetching venue with id: {}", id);

        Venue venue = venueRepository.findById(id)
                .orElseThrow(() -> new NotFoundException("Venue not found"));

        return toResponseDto(venue);
    }

    @Transactional
    public List<VenueResponseDto> getAll() {
        log.info("Fetching all venues");
        return venueRepository.findAll().stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Caching(evict = {
            @CacheEvict(cacheNames = "venuesById", key = "#id"),
            @CacheEvict(cacheNames = "venueSearch", allEntries = true)
    })
    @Transactional
    public void deleteById(Integer id) {
        if (id == null || id < 1) {
            throw new IllegalArgumentException("Venue id must be positive");
        }

        if (!venueRepository.existsById(id)) {
            throw new NotFoundException("Venue not found");
        }

        log.info("Deleting venue with id: {}", id);
        venueRepository.deleteById(id);
    }

    @Caching(evict = {
            @CacheEvict(cacheNames = "venuesById", allEntries = true),
            @CacheEvict(cacheNames = "venueSearch", allEntries = true)
    })
    @Transactional
    public long deleteByFilter(VenueDeleteRequestDto requestDto) {
        Specification<Venue> spec = Specification
                .where(VenueSpecification.hasTownId(requestDto.getTownId()))
                .and(VenueSpecification.hasPlace(requestDto.getPlace()))
                .and(VenueSpecification.hasCapacityGreaterThanOrEqual(requestDto.getMinCapacity()))
                .and(VenueSpecification.hasCapacityLessThanOrEqual(requestDto.getMaxCapacity()));

        log.debug("Delete by filter: townId={}, place={}, minCapacity={}, maxCapacity={}",
                requestDto.getTownId(),
                requestDto.getPlace(),
                requestDto.getMinCapacity(),
                requestDto.getMaxCapacity());

        List<Venue> venues = venueRepository.findAll(spec);
        long count = venues.size();

        log.info("Delete by filter amount: {}", count);
        venueRepository.deleteAll(venues);

        return count;
    }

    @Cacheable(
            cacheNames = "venueSearch",
            key = "{#filter.townId, #filter.place, #filter.minCapacity, #filter.maxCapacity, #page, #size}"
    )
    @Transactional
    public List<VenueResponseDto> searchByFilter(VenueSearchRequestDto filter, int page, int size) {
        if (page < 1) {
            throw new IllegalArgumentException("Page must be >= 1");
        }
        if (size < 1) {
            throw new IllegalArgumentException("Size must be >= 1");
        }

        Specification<Venue> spec = Specification.
                where(VenueSpecification.hasTownId(filter.getTownId())).
                and(VenueSpecification.hasPlace(filter.getPlace())).
                and(VenueSpecification.hasCapacityGreaterThanOrEqual(filter.getMinCapacity())).
                and(VenueSpecification.hasCapacityLessThanOrEqual(filter.getMaxCapacity()));


        log.debug("Search by filter: townId={}, place={}, minCapacity={}, maxCapacity={}, page={}, size={}",
                filter.getTownId(),
                filter.getPlace(),
                filter.getMinCapacity(),
                filter.getMaxCapacity(),
                page,
                size);

        Pageable pageable = PageRequest.of(page - 1, size);

        return venueRepository.findAll(spec, pageable)
                .stream()
                .map(this::toResponseDto)
                .toList();
    }

    @Caching(
            put = {
                    @CachePut(cacheNames = "venuesById", key = "#result.id")
            },
            evict = {
                    @CacheEvict(cacheNames = "venueSearch", allEntries = true)
            }
    )
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

        log.info("Updating venue with id: {}", venue.getId());
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