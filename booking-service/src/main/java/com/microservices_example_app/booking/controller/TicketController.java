package com.microservices_example_app.booking.controller;

import com.microservices_example_app.booking.dto.*;
import com.microservices_example_app.booking.service.TicketService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/booking/tickets")
@RequiredArgsConstructor
@Slf4j
public class TicketController {

    private final TicketService ticketService;

    @PostMapping
    public TicketResponseDto create(@Valid @RequestBody TicketCreateRequestDto requestDto) {
        log.info("Creating new ticket for event id: {}", requestDto.getEventId());
        return ticketService.create(requestDto);
    }

    @GetMapping("/{id}")
    public TicketResponseDto getById(@PathVariable Integer id) {
        log.info("Fetching ticket with id: {}", id);
        return ticketService.getById(id);
    }

    @GetMapping("/search")
    public List<TicketResponseDto> searchByFilter(@Valid @ModelAttribute TicketSearchRequestDto filter,
                                                  @RequestParam(defaultValue = "1") int page,
                                                  @RequestParam(defaultValue = "10") int size) {
        log.info("Searching tickets by filter: eventId={}, userId={}, zone={}", 
                filter.getEventId(), filter.getUserId(), filter.getZone());
        return ticketService.searchByFilter(filter, page, size);
    }

    @PutMapping("/{id}")
    public TicketResponseDto updateById(@PathVariable Integer id,
                                        @Valid @RequestBody TicketUpdateRequestDto requestDto) {
        log.info("Updating ticket with id: {}", id);
        requestDto.setId(id);
        return ticketService.updateTicketById(requestDto);
    }

    @DeleteMapping("/{id}")
    public void deleteById(@PathVariable Integer id) {
        log.info("Deleting ticket with id: {}", id);
        ticketService.deleteById(id);
    }

    @DeleteMapping("/search")
    public long deleteByFilter(@Valid @RequestBody TicketDeleteRequestDto requestDto) {
        log.info("Deleting tickets by filter: eventId={}, userId={}", requestDto.getEventId(), requestDto.getUserId());
        return ticketService.deleteByFilter(requestDto);
    }
}