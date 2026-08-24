package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.VenueService;
import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@RestController
@RequestMapping("/booking/venues")
@RequiredArgsConstructor
@Slf4j
public class VenueController {

    private final VenueService venueService;
    private final JwtRequestUserExtractor jwtRequestUserExtractor;

    @PostMapping
    public VenueResponseDto create(@Valid @RequestBody VenueCreateRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Creating new venue in town id: {}", requestDto.getTownId());
        return venueService.create(requestDto);
    }

    @GetMapping
    public List<VenueResponseDto> getAll() {
        log.info("Fetching all venues");
        return venueService.getAll();
    }

    @GetMapping("/{id}")
    public VenueResponseDto getById(@PathVariable Integer id) {
        log.info("Fetching venue with id: {}", id);
        return venueService.getById(id);
    }

    @GetMapping("/search")
    public List<VenueResponseDto> searchByFilter(@Valid @ModelAttribute VenueSearchRequestDto filter,
                                                 @RequestParam(defaultValue = "1") int page,
                                                 @RequestParam(defaultValue = "10") int size) {
        log.info("Searching venues by filter: townId={}, place={}, minCapacity={}, maxCapacity={}", 
                filter.getTownId(), filter.getPlace(), filter.getMinCapacity(), filter.getMaxCapacity());
        return venueService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public VenueResponseDto updateById(@PathVariable Integer id,
                                       @Valid @RequestBody VenueUpdateRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Updating venue with id: {}", id);
        requestDto.setId(id);
        return venueService.updateVenueById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        requireEventManagerOrAdmin();
        log.info("Deleting venue with id: {}", id);
        venueService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody VenueDeleteRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Deleting venues by filter: townId={}, place={}", requestDto.getTownId(), requestDto.getPlace());
        return venueService.deleteByFilter(requestDto);
    }

    private void requireEventManagerOrAdmin() {
        if (!jwtRequestUserExtractor.isEventManagerOrAdmin()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Requires EVENT_MANAGER or ADMIN role");
        }
    }
}
