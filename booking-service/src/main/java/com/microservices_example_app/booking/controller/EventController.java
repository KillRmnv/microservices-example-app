package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.EventService;
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
@RequestMapping("/booking/events")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Events", description = "Event catalog management")
public class EventController {

    private final EventService eventService;
    private final JwtRequestUserExtractor jwtRequestUserExtractor;

    @Operation(summary = "Create a new event")
    @PostMapping
    public EventResponseDto create(@Valid @RequestBody EventCreateRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Creating new event: {}", requestDto.getTitle());
        return eventService.create(requestDto);
    }

    @Operation(summary = "Get an event by id")
    @GetMapping("/{id}")
    public EventResponseDto getById(@Parameter(description = "Event id") @PathVariable Long id) {
        log.info("Fetching event with id: {}", id);
        return eventService.getById(id);
    }

    @Operation(summary = "List all events")
    @GetMapping
    public List<EventResponseDto> getAll() {
        log.info("Fetching all events");
        return eventService.getAll();
    }

    @Operation(summary = "Search events by filter with pagination")
    @GetMapping("/search")
    public List<EventResponseDto> searchByFilter(@Valid @ModelAttribute EventSearchRequestDto filter,
                                                 @Parameter(description = "One-based page number") @RequestParam(defaultValue = "1") int page,
                                                 @Parameter(description = "Page size") @RequestParam(defaultValue = "10") int size) {
        log.info("Fetching by filter page:{} , dto:{}",page,filter);
        return eventService.searchByFilter(filter, page, size);
    }

    @Operation(summary = "Update an event")
    @PutMapping("/{id}")
    public EventResponseDto updateById(@Parameter(description = "Event id") @PathVariable Long id,
                                       @Valid @RequestBody EventUpdateRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Update by id:{} , dto:{}",id,requestDto);
        requestDto.setId(id);
        return eventService.updateEventById(requestDto);
    }

    @Operation(summary = "Delete an event")
    @DeleteMapping("/{id}")
    public void deleteById(@Parameter(description = "Event id") @PathVariable Long id) {
        requireEventManagerOrAdmin();
        log.info("Deleting event with id: {}", id);
        eventService.deleteById(id);
    }

    @Operation(summary = "Delete events matching a filter")
    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody EventDeleteRequestDto requestDto) {
        requireEventManagerOrAdmin();
        log.info("Delete by filter:{}",requestDto);
        return eventService.deleteByFilter(requestDto);
    }

    private void requireEventManagerOrAdmin() {
        if (!jwtRequestUserExtractor.isEventManagerOrAdmin()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Requires EVENT_MANAGER or ADMIN role");
        }
    }
}
