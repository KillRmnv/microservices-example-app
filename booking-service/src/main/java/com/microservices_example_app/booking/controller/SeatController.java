package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.SeatService;
import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@RestController
@RequestMapping("/booking/seats")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Seats", description = "Venue seat management")
public class SeatController {

    private final SeatService seatService;
    private final JwtRequestUserExtractor jwtRequestUserExtractor;

    @Operation(summary = "Create a new seat")
    @PostMapping
    public SeatResponseDto create(@Valid @RequestBody SeatCreateRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Creating new seat in venue id: {}", requestDto.getVenueId());
        return seatService.create(requestDto);
    }

    @Operation(summary = "Get a seat by id")
    @GetMapping("/{id}")
    public SeatResponseDto getById(@Parameter(description = "Seat id") @PathVariable Integer id) {
        log.info("Fetching seat with id: {}", id);
        return seatService.getById(id);
    }

    @Operation(summary = "Search seats by filter with pagination")
    @GetMapping("/search")
    public List<SeatResponseDto> searchByFilter(@Valid @ModelAttribute SeatSearchRequestDto filter,
                                                @Parameter(description = "One-based page number") @RequestParam(defaultValue = "1") int page,
                                                @Parameter(description = "Page size") @RequestParam(defaultValue = "10") int size) {
        log.info("Searching seats by filter: venueId={}, sector={}, row={}, number={}",
                filter.getVenueId(), filter.getSector(), filter.getRow(), filter.getNumber());
        return seatService.searchByFilter(filter, page, size);
    }

    @Operation(summary = "Update a seat")
    @PutMapping("/{id}")
    public SeatResponseDto updateById(@Parameter(description = "Seat id") @PathVariable Integer id,
                                      @Valid @RequestBody SeatUpdateRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Updating seat with id: {}", id);
        requestDto.setId(id);
        return seatService.updateSeatById(requestDto);
    }

    @Operation(summary = "Delete a seat")
    @DeleteMapping("/{id}")
    public void deleteById(@Parameter(description = "Seat id") @PathVariable Integer id) {
        requireEventManagerOrAdmin();
        log.info("Deleting seat with id: {}", id);
        seatService.deleteById(id);
    }

    @Operation(summary = "Delete seats matching a filter")
    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody SeatDeleteRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Deleting seats by filter: venueId={}, sector={}", 
                requestDto.getVenueId(), requestDto.getSector());
        return seatService.deleteByFilter(requestDto);
    }

    private void requireEventManagerOrAdmin() {
        if (!jwtRequestUserExtractor.isEventManagerOrAdmin()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Requires EVENT_MANAGER or ADMIN role");
        }
    }
}
