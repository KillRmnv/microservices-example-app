package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.TicketService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/tickets")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Tickets", description = "General-admission ticket management")
public class TicketController {

    private final TicketService ticketService;

    @Operation(summary = "Create a new ticket")
    @PostMapping
    public TicketResponseDto create(@Valid @RequestBody TicketCreateRequestDto requestDto) {
        log.info("Creating new ticket for event id: {}", requestDto.getEventId());
        return ticketService.create(requestDto);
    }

    @Operation(summary = "Get a ticket by id")
    @GetMapping("/{id}")
    public TicketResponseDto getById(@Parameter(description = "Ticket id") @PathVariable Integer id) {
        log.info("Fetching ticket with id: {}", id);
        return ticketService.getById(id);
    }

    @Operation(summary = "Search tickets by filter with pagination")
    @GetMapping("/search")
    public List<TicketResponseDto> searchByFilter(@Valid @ModelAttribute TicketSearchRequestDto filter,
                                                  @Parameter(description = "One-based page number") @RequestParam(defaultValue = "1") int page,
                                                  @Parameter(description = "Page size") @RequestParam(defaultValue = "10") int size) {
        log.info("Searching tickets by filter: eventId={}, userId={}, zone={}", 
                filter.getEventId(), filter.getUserId(), filter.getZone());
        return ticketService.searchByFilter(filter, page, size);
    }

    @Operation(summary = "Update a ticket")
    @PutMapping("/{id}")
    public TicketResponseDto updateById(@Parameter(description = "Ticket id") @PathVariable Integer id,
                                        @Valid @RequestBody TicketUpdateRequestDto requestDto) {
        log.info("Updating ticket with id: {}", id);
        requestDto.setId(id);
        return ticketService.updateTicketById(requestDto);
    }

    @Operation(summary = "Delete a ticket")
    @DeleteMapping("/{id}")
    public void deleteById(@Parameter(description = "Ticket id") @PathVariable Integer id) {
        log.info("Deleting ticket with id: {}", id);
        ticketService.deleteById(id);
    }

    @Operation(summary = "Delete tickets matching a filter")
    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody TicketDeleteRequestDto requestDto) {
        log.info("Deleting tickets by filter: eventId={}, userId={}", requestDto.getEventId(), requestDto.getUserId());
        return ticketService.deleteByFilter(requestDto);
    }
    @Operation(summary = "Refund a ticket")
    @PostMapping("/{id}/refund")
    public TicketResponseDto refund(@Parameter(description = "Ticket id") @PathVariable Integer id) {
        log.info("Refunding ticket with id: {}", id);
        return ticketService.refund(id);
    }
}