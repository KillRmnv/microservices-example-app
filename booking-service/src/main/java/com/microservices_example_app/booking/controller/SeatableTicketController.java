package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.SeatableTicketService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/seatable-tickets")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Seatable tickets", description = "Tickets bound to a specific seat")
public class SeatableTicketController {

    private final SeatableTicketService seatableTicketService;

    @Operation(summary = "Create a new seatable ticket")
    @PostMapping
    public SeatableTicketResponseDto create(@Valid @RequestBody SeatableTicketCreateRequestDto requestDto) {
        log.info("Creating seatable ticket for event id: {}", requestDto.getEventId());
        return seatableTicketService.create(requestDto);
    }

    @Operation(summary = "Get a seatable ticket by id")
    @GetMapping("/{id}")
    public SeatableTicketResponseDto getById(@Parameter(description = "Seatable ticket id") @PathVariable Integer id) {
        log.info("Fetching seatable ticket with id: {}", id);
        return seatableTicketService.getById(id);
    }

    @Operation(summary = "Search seatable tickets by filter with pagination")
    @GetMapping("/search")
    public List<SeatableTicketResponseDto> searchByFilter(@Valid @ModelAttribute SeatableTicketSearchRequestDto filter,
                                                          @Parameter(description = "One-based page number") @RequestParam(defaultValue = "1") int page,
                                                          @Parameter(description = "Page size") @RequestParam(defaultValue = "10") int size) {
        log.info("Searching seatable tickets by filter: eventId={}, userId={}, sector={}", 
                filter.getEventId(), filter.getUserId(), filter.getSector());
        return seatableTicketService.searchByFilter(filter, page, size);
    }

    @Operation(summary = "Update a seatable ticket")
    @PutMapping("/{id}")
    public SeatableTicketResponseDto updateById(@Parameter(description = "Seatable ticket id") @PathVariable Integer id,
                                                @Valid @RequestBody SeatableTicketUpdateRequestDto requestDto) {
        log.info("Updating seatable ticket with id: {}", id);
        requestDto.setId(id);
        return seatableTicketService.updateSeatableTicketById(requestDto);
    }
    @Operation(summary = "Refund a seatable ticket")
    @PostMapping("/{id}/refund")
    public SeatableTicketResponseDto refund(@Parameter(description = "Seatable ticket id") @PathVariable Integer id) {
        log.info("Refunding seatable ticket with id: {}", id);
        return seatableTicketService.refund(id);
    }
    @Operation(summary = "Delete a seatable ticket")
    @DeleteMapping("/{id}")
    public void deleteById(@Parameter(description = "Seatable ticket id") @PathVariable Integer id) {
        log.info("Deleting seatable ticket with id: {}", id);
        seatableTicketService.deleteById(id);
    }

    @Operation(summary = "Delete seatable tickets matching a filter")
    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody SeatableTicketDeleteRequestDto requestDto) {
        log.info("Deleting seatable tickets by filter: eventId={}, userId={}", 
                requestDto.getEventId(), requestDto.getUserId());
        return seatableTicketService.deleteByFilter(requestDto);
    }
}