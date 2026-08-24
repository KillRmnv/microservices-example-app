package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.SeatService;
import com.microservices_example_app.booking.utils.JwtRequestUserExtractor;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@RestController
@RequestMapping("/booking/seats")
@RequiredArgsConstructor
@Slf4j
public class SeatController {

    private final SeatService seatService;
    private final JwtRequestUserExtractor jwtRequestUserExtractor;

    @PostMapping
    public SeatResponseDto create(@Valid @RequestBody SeatCreateRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Creating new seat in venue id: {}", requestDto.getVenueId());
        return seatService.create(requestDto);
    }

    @GetMapping("/{id}")
    public SeatResponseDto getById(@PathVariable Integer id) {
        log.info("Fetching seat with id: {}", id);
        return seatService.getById(id);
    }

    @GetMapping("/search")
    public List<SeatResponseDto> searchByFilter(@Valid @ModelAttribute SeatSearchRequestDto filter,
                                                @RequestParam(defaultValue = "1") int page,
                                                @RequestParam(defaultValue = "10") int size) {
        log.info("Searching seats by filter: venueId={}, sector={}, row={}, number={}",
                filter.getVenueId(), filter.getSector(), filter.getRow(), filter.getNumber());
        return seatService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public SeatResponseDto updateById(@PathVariable Integer id,
                                      @Valid @RequestBody SeatUpdateRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Updating seat with id: {}", id);
        requestDto.setId(id);
        return seatService.updateSeatById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        requireEventManagerOrAdmin();
        log.info("Deleting seat with id: {}", id);
        seatService.deleteById(id);
    }

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
